"""Gradio web UI for the Weber knowledge base.

Usage:
    python app.py                  # default: http://127.0.0.1:7860
    python app.py --port 8080      # custom port
    python app.py --share          # create public link (temporary)
"""

import sys
import os
import argparse
import gradio as gr

# Ensure we can import from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from embeddings import create_embedding_model
from store import hierarchical_search, collection_stats, list_sources_grouped
from query import (
    _format_source, format_context, _get_llm_client, SYSTEM_PROMPT,
    resolve_book_name, resolve_collection_name,
)


# ── Global (loaded once at startup) ──────────────────────────────────────────
embed_model = None


def _ensure_model():
    global embed_model
    if embed_model is None:
        embed_model = create_embedding_model()


# ── Chat logic ───────────────────────────────────────────────────────────────

def _do_search(query: str, source_filter: str | None,
               category_filter: str | None,
               source_exclude: list[str] | None = None) -> str:
    """Search-only: retrieve and format results, no LLM."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 `python setup.sh` 或 `python import_data.py`。"

    q_emb = embed_model.embed_query(query)
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude_list=source_exclude,
        query_text=query,
    )

    if not sections and not chunks:
        return "未找到相关内容。"

    lines = []
    if sections:
        lines.append("### 相关章节")
        for i, s in enumerate(sections):
            dist = s.get("distance")
            score = f" [相似度: {1 - dist:.4f}]" if dist is not None else ""
            lines.append(f"\n**{i+1}.{score}**")
            lines.append(_format_source(s.get("metadata", {})))
            lines.append(s["text"][:3000])

    if chunks:
        lines.append("\n### 相关段落")
        for i, c in enumerate(chunks):
            dist = c.get("distance")
            score = f" [相似度: {1 - dist:.4f}]" if dist is not None else ""
            lines.append(f"\n**{i+1}.{score}**")
            lines.append(_format_source(c.get("metadata", {})))
            lines.append(c["text"])

    # Source summary
    sources = set()
    for item in (chunks or []) + (sections or []):
        meta = item.get("metadata", {})
        pub = meta.get("publisher", meta.get("edition", "?"))
        sources.add(f"《{meta.get('book', '?')}》（{pub}）")

    lines.append(f"\n---\n检索到 {len(sections)} 章节、{len(chunks)} 段落（来自 {len(sources)} 个来源）")
    return "\n".join(lines)


def _do_qa(query: str, history: list[dict],
           source_filter: str | None,
           category_filter: str | None,
           source_exclude: list[str] | None = None) -> tuple[str, list[dict]]:
    """Full RAG + LLM Q&A. Returns (answer, new_history)."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 `python setup.sh` 或 `python import_data.py`。", history

    q_emb = embed_model.embed_query(query)
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude_list=source_exclude,
        query_text=query,
    )

    if not sections and not chunks:
        return "未找到相关内容。", history

    context = format_context(sections, chunks)
    client = _get_llm_client()

    if not history:
        # First question
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"参考资料：\n\n{context}\n\n问题：{query}"},
        ]
    else:
        # Follow-up: append new context + question to existing history
        history.append({
            "role": "user",
            "content": f"参考资料：\n\n{context}\n\n追问：{query}",
        })
        messages = history

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=messages,
    )
    answer = response.choices[0].message.content

    # Append assistant reply to history
    new_history = list(messages)
    new_history.append({"role": "assistant", "content": answer})

    return answer, new_history


# ── Gradio interface ─────────────────────────────────────────────────────────

def _handle_chat(message: str, chat_history: list, llm_state,
                 search_mode: bool, src_filter: str, cat_filter: str,
                 exc_filter: list):
    """Process one chat turn.

    Returns: (updated_chat_history, empty_input, updated_llm_state)
    """
    _ensure_model()

    source = src_filter.strip() if src_filter else None
    category = cat_filter.strip() if cat_filter else None
    excludes = [e for e in (exc_filter or []) if e]
    excludes = excludes if excludes else None
    chat_history = list(chat_history) if chat_history else []

    # Handle / commands
    msg = message.strip()
    if msg in ("/new", "/clear"):
        chat_history.append({"role": "user", "content": "/new"})
        chat_history.append({"role": "assistant", "content": "对话已重置。"})
        return chat_history, "", None

    if msg == "/help":
        chat_history.append({"role": "user", "content": "/help"})
        chat_history.append({"role": "assistant", "content":
            "**命令：**\n"
            "- `/new` — 开始新话题\n"
            "- 左侧可切换「仅搜索」模式和筛选条件\n"
            "- 修改筛选条件后建议 `/new` 重置对话"
        })
        return chat_history, "", llm_state

    if search_mode:
        answer = _do_search(message, source_filter=source,
                            category_filter=category,
                            source_exclude=excludes)
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": answer})
        return chat_history, "", llm_state
    else:
        state = list(llm_state) if llm_state else []
        answer, new_state = _do_qa(message, state,
                                   source_filter=source,
                                   category_filter=category,
                                   source_exclude=excludes)
        chat_history.append({"role": "user", "content": message})
        chat_history.append({"role": "assistant", "content": answer})
        return chat_history, "", new_state


def build_ui():
    """Build and return the Gradio Blocks app."""
    sources = [""] + [g["source_name"] for g in list_sources_grouped(min_chunks=0)]
    categories = [""] + config.CATEGORIES

    with gr.Blocks(title="Weber 知识库") as demo:
        gr.Markdown("# Weber 知识库查询")
        gr.Markdown("基于马克斯·韦伯著作、传记与研究文献的 RAG 问答系统。")

        # Hidden LLM conversation state
        llm_state = gr.State(None)

        with gr.Row():
            # ── Sidebar: filters ──
            with gr.Column(scale=1, min_width=220):
                gr.Markdown("### 筛选条件")
                src_dd = gr.Dropdown(
                    choices=sources, value="", label="来源筛选",
                    info="按具体书或合集过滤",
                )
                cat_dd = gr.Dropdown(
                    choices=categories, value="", label="分类筛选",
                    info="韦伯著述 / 传记与介绍 / 思想研究与讨论 / 相关史料",
                )
                exc_dd = gr.Dropdown(
                    choices=sources[1:], value=[], label="屏蔽来源",
                    info="选择不想搜索的书或合集（可多选）",
                    multiselect=True,
                )
                search_toggle = gr.Checkbox(
                    value=False, label="仅搜索（跳过 LLM 问答）",
                    info="开启后只检索不生成回答",
                )

                gr.Markdown("### 排序加权")
                div_slider = gr.Slider(
                    minimum=0, maximum=0.5, value=0.15, step=0.01,
                    label="每本书首位加权",
                    info="每本书第一个结果的匹配分数加成（0 = 关闭）",
                )
                lang_slider = gr.Slider(
                    minimum=0, maximum=0.3, value=0.10, step=0.01,
                    label="跨语言加权",
                    info="不同语言结果的分数加成（0 = 关闭）",
                )

                gr.Markdown("---")
                gr.Markdown(
                    "**使用提示**\n\n"
                    "- 输入 `/new` 重置对话\n"
                    "- 修改筛选后建议 `/new` 重置\n"
                    "- 「仅搜索」模式不消耗 API\n\n"
                    "**首次使用？**\n"
                    "运行 `python setup.sh` 或 `setup.bat`"
                )

            # ── Main: chat ──
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    value=[],
                    height=550,
                )
                msg_input = gr.Textbox(
                    placeholder="输入你的问题，按 Enter 发送（输入 /new 重置对话）...",
                    show_label=False,
                    container=False,
                )
                gr.Examples(
                    examples=[
                        "韦伯如何定义'理想类型'？",
                        "新教伦理与资本主义精神的核心论点是什么？",
                        "韦伯对官僚制的分析",
                    ],
                    inputs=[msg_input],
                )

        # ── Event handlers ──
        msg_input.submit(
            fn=_handle_chat,
            inputs=[msg_input, chatbot, llm_state, search_toggle, src_dd, cat_dd,
                    exc_dd],
            outputs=[chatbot, msg_input, llm_state],
        )

        # Sliders update config in-place, no need to pass through chat
        div_slider.change(fn=lambda v: setattr(config, "DIVERSITY_BONUS", v),
                          inputs=[div_slider])
        lang_slider.change(fn=lambda v: setattr(config, "CROSS_LANG_BONUS", v),
                           inputs=[lang_slider])

    return demo


def main():
    parser = argparse.ArgumentParser(description="Weber Knowledge Base — Web UI")
    parser.add_argument("--port", type=int, default=7860, help="Server port")
    parser.add_argument("--share", action="store_true",
                        help="Create a public Gradio share link")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    print("Loading embedding model...", file=sys.stderr, end=" ", flush=True)
    _ensure_model()
    print("done", file=sys.stderr)

    stats = collection_stats()
    print(f"Database: {stats['sections']} sections, {stats['chunks']} chunks",
          file=sys.stderr)

    demo = build_ui()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
