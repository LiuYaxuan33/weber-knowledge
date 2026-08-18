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
from store import collection_stats, list_sources_grouped
from index_manifest import validate_index_compatibility
from rag_service import (
    RetrievalOptions,
    answer_question,
    format_search_results,
    retrieve,
)


# ── Global (loaded once at startup) ──────────────────────────────────────────
embed_model = None


def _ensure_model():
    global embed_model
    if embed_model is None:
        embed_model = create_embedding_model()
        if collection_stats()["chunks"] > 0:
            validate_index_compatibility(embed_model)


# ── Chat logic ───────────────────────────────────────────────────────────────

def _do_search(query: str, source_filter: list[str] | None,
               category_filter: list[str] | None,
               source_exclude: list[str] | None = None,
               diversity_bonus: float = config.DIVERSITY_BONUS,
               cross_lang_bonus: float = config.CROSS_LANG_BONUS) -> str:
    """Search-only: retrieve and format results, no LLM."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 `python setup.sh` 或 `python import_data.py`。"

    options = RetrievalOptions(
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude_list=source_exclude,
        diversity_bonus=diversity_bonus,
        cross_lang_bonus=cross_lang_bonus,
    )
    sections, chunks = retrieve(query, embed_model, options)
    return format_search_results(sections, chunks)


def _do_qa(query: str, history: list[dict],
           source_filter: list[str] | None,
           category_filter: list[str] | None,
           source_exclude: list[str] | None = None,
           diversity_bonus: float = config.DIVERSITY_BONUS,
           cross_lang_bonus: float = config.CROSS_LANG_BONUS) -> tuple[str, list[dict]]:
    """Full RAG + LLM Q&A. Returns (answer, new_history)."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 `python setup.sh` 或 `python import_data.py`。", history

    options = RetrievalOptions(
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude_list=source_exclude,
        diversity_bonus=diversity_bonus,
        cross_lang_bonus=cross_lang_bonus,
    )
    return answer_question(query, embed_model, history=history, options=options)


# ── Gradio interface ─────────────────────────────────────────────────────────

def _handle_chat(message: str, chat_history: list, llm_state,
                 search_mode: bool, src_filter: list, cat_filter: list,
                 exc_filter: list, div_bonus: float, lang_bonus: float):
    """Process one chat turn."""
    source = [s for s in (src_filter or []) if s] or None
    category = [c for c in (cat_filter or []) if c] or None
    excludes = [e for e in (exc_filter or []) if e] or None
    chat_history = list(chat_history) if chat_history else []

    # Handle / commands
    msg = message.strip()
    if not msg:
        return chat_history, "", llm_state
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

    try:
        _ensure_model()
        if search_mode:
            answer = _do_search(
                message,
                source_filter=source,
                category_filter=category,
                source_exclude=excludes,
                diversity_bonus=div_bonus,
                cross_lang_bonus=lang_bonus,
            )
            new_state = llm_state
        else:
            state = list(llm_state) if llm_state else []
            answer, new_state = _do_qa(
                message,
                state,
                source_filter=source,
                category_filter=category,
                source_exclude=excludes,
                diversity_bonus=div_bonus,
                cross_lang_bonus=lang_bonus,
            )
    except Exception as error:
        print(f"Request failed: {error}", file=sys.stderr)
        answer = f"请求失败：{error}"
        new_state = llm_state

    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": answer})
    return chat_history, "", new_state


# ── Custom CSS ────────────────────────────────────────────────────────────────
CSS = """
.sidebar-column { overflow-y: auto !important; max-height: 100vh; }
.main-column { overflow: hidden !important; }
.chatbot-container { height: calc(100vh - 220px) !important; }
"""


def build_ui():
    """Build and return the Gradio Blocks app."""
    sources = [""] + [g["source_name"] for g in list_sources_grouped(min_chunks=0)]
    categories = [""] + config.CATEGORIES

    with gr.Blocks(title="Weber 知识库", fill_height=True) as demo:
        gr.Markdown("# Weber 知识库查询")
        gr.Markdown("基于马克斯·韦伯著作、传记与研究文献的 RAG 问答系统。")

        # Hidden LLM conversation state
        llm_state = gr.State(None)

        with gr.Row(equal_height=True):
            # ── Sidebar: filters ──
            with gr.Column(scale=1, min_width=220, elem_classes="sidebar-column"):
                gr.Markdown("### 筛选条件")
                src_dd = gr.Dropdown(
                    choices=sources[1:], value=[], label="来源筛选",
                    info="按具体书或合集过滤（可多选，空 = 全部）",
                    multiselect=True,
                )
                cat_dd = gr.Dropdown(
                    choices=categories[1:], value=[], label="分类筛选",
                    info="韦伯著述 / 传记与介绍 / 思想研究与讨论 / 相关史料（可多选，空 = 全部）",
                    multiselect=True,
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
                    minimum=0, maximum=0.5, value=config.DIVERSITY_BONUS, step=0.01,
                    label="每本书首位加权",
                    info="每本书第一个结果的匹配分数加成（0 = 关闭）",
                )
                lang_slider = gr.Slider(
                    minimum=0, maximum=0.3, value=config.CROSS_LANG_BONUS, step=0.01,
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
            with gr.Column(scale=3, elem_classes="main-column"):
                chatbot = gr.Chatbot(
                    value=[],
                    elem_classes="chatbot-container",
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
                    exc_dd, div_slider, lang_slider],
            outputs=[chatbot, msg_input, llm_state],
        )

    return demo.queue(default_concurrency_limit=1, max_size=16)


def main():
    parser = argparse.ArgumentParser(description="Weber Knowledge Base — Web UI")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "7860")),
                        help="Server port")
    parser.add_argument("--share", action="store_true",
                        help="Create a public Gradio share link")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
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
        css=CSS,
        theme=gr.themes.Soft(),
        inbrowser=(
            os.environ.get("WEBER_NO_BROWSER") != "1"
            and args.host in {"127.0.0.1", "localhost"}
        ),
    )


if __name__ == "__main__":
    main()
