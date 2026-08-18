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
:root {
    --weber-bg: #f5f3ee;
    --weber-surface: #fffefb;
    --weber-text: #20211f;
    --weber-muted: #777970;
    --weber-line: #deddd6;
    --weber-accent: #242722;
}

html, body, #root, .gradio-container {
    min-height: 100%;
    background: var(--weber-bg) !important;
}

body {
    color: var(--weber-text);
}

.gradio-container {
    max-width: none !important;
    margin: 0 !important;
}

.app-shell {
    box-sizing: border-box;
    width: min(100%, 920px) !important;
    height: 100dvh;
    margin: 0 auto !important;
    padding: clamp(22px, 4vw, 44px) clamp(16px, 3vw, 28px) 20px !important;
    gap: 14px !important;
}

.app-header {
    align-items: center !important;
    flex: 0 0 auto !important;
}

.brand-block {
    min-width: 0;
}

.brand-title {
    margin: 0;
    font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
    font-size: clamp(27px, 4vw, 36px);
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.05;
}

.brand-title span {
    margin-left: 0.32em;
    color: var(--weber-muted);
    font-family: inherit;
    font-size: 0.55em;
    font-weight: 400;
    letter-spacing: 0.08em;
}

.brand-subtitle p {
    margin: 6px 0 0 !important;
    color: var(--weber-muted);
    font-size: 13px;
}

.new-chat {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: auto !important;
}

.new-chat button {
    min-width: auto !important;
    border-color: transparent !important;
    background: transparent !important;
    color: var(--weber-muted) !important;
    box-shadow: none !important;
}

.new-chat button:hover {
    border-color: var(--weber-line) !important;
    background: rgba(255, 255, 255, 0.45) !important;
    color: var(--weber-text) !important;
}

#weber-chat {
    min-height: 0 !important;
    height: auto !important;
    flex: 1 1 auto !important;
    overflow: hidden !important;
    border: 1px solid var(--weber-line) !important;
    border-radius: 18px !important;
    background: rgba(255, 254, 251, 0.74) !important;
    box-shadow: none !important;
}

#weber-chat .message {
    max-width: min(84%, 700px) !important;
    border: 0 !important;
    border-radius: 15px !important;
    box-shadow: none !important;
}

#weber-chat .message.user {
    background: var(--weber-accent) !important;
    color: #fffefb !important;
}

#weber-chat .message.bot {
    background: #ebe9e2 !important;
    color: var(--weber-text) !important;
}

.composer {
    align-items: stretch !important;
    flex: 0 0 auto !important;
    gap: 10px !important;
}

#question-input {
    min-width: 0 !important;
    border: 1px solid var(--weber-line) !important;
    border-radius: 14px !important;
    background: var(--weber-surface) !important;
    box-shadow: none !important;
}

#question-input:focus-within {
    border-color: #a7a89f !important;
    box-shadow: 0 0 0 3px rgba(36, 39, 34, 0.06) !important;
}

#question-input textarea {
    padding: 12px 14px !important;
    font-size: 15px !important;
}

#send-button {
    flex: 0 0 82px !important;
    width: 82px !important;
    min-width: 82px !important;
    border: 0 !important;
    border-radius: 14px !important;
    background: var(--weber-accent) !important;
    color: #fffefb !important;
    box-shadow: none !important;
}

#send-button:hover {
    background: #383c35 !important;
}

#search-settings {
    flex: 0 0 auto !important;
    border: 0 !important;
    background: transparent !important;
    box-shadow: none !important;
}

#search-settings > .label-wrap {
    padding: 4px 2px !important;
    color: var(--weber-muted) !important;
    font-size: 13px !important;
}

.settings-grid {
    gap: 10px !important;
}

.settings-grid > div {
    min-width: 190px !important;
}

footer {
    display: none !important;
}

@media (max-width: 640px) {
    .app-shell {
        padding-top: 18px !important;
        padding-bottom: 12px !important;
        gap: 10px !important;
    }

    .brand-subtitle {
        display: none;
    }

    #weber-chat {
        border-radius: 15px !important;
    }

    #send-button {
        flex-basis: 68px !important;
        width: 68px !important;
        min-width: 68px !important;
    }
}
"""


def _clear_chat():
    """Clear both visible messages and hidden LLM conversation state."""
    return [], "", None


def build_ui():
    """Build and return the Gradio Blocks app."""
    sources = [g["source_name"] for g in list_sources_grouped(min_chunks=0)]

    with gr.Blocks(title="Weber 知识库", fill_height=True) as demo:
        # Hidden LLM conversation state
        llm_state = gr.State(None)
        div_bonus = gr.State(config.DIVERSITY_BONUS)
        lang_bonus = gr.State(config.CROSS_LANG_BONUS)

        with gr.Column(elem_classes="app-shell"):
            with gr.Row(elem_classes="app-header"):
                with gr.Column(scale=1, elem_classes="brand-block"):
                    gr.HTML(
                        '<h1 class="brand-title">Weber<span>知识库</span></h1>'
                    )
                    gr.Markdown(
                        "聚焦马克斯·韦伯的著作与研究。",
                        elem_classes="brand-subtitle",
                    )
                clear_button = gr.Button(
                    "新对话",
                    variant="secondary",
                    size="sm",
                    elem_classes="new-chat",
                )

            chatbot = gr.Chatbot(value=[], elem_id="weber-chat")

            with gr.Row(elem_classes="composer"):
                msg_input = gr.Textbox(
                    placeholder="问一个关于韦伯的问题",
                    show_label=False,
                    container=False,
                    lines=1,
                    max_lines=6,
                    elem_id="question-input",
                )
                send_button = gr.Button(
                    "发送",
                    variant="primary",
                    elem_id="send-button",
                )

            with gr.Accordion("检索设置", open=False, elem_id="search-settings"):
                with gr.Row(elem_classes="settings-grid"):
                    src_dd = gr.Dropdown(
                        choices=sources,
                        value=[],
                        label="包含来源",
                        multiselect=True,
                    )
                    cat_dd = gr.Dropdown(
                        choices=config.CATEGORIES,
                        value=[],
                        label="分类",
                        multiselect=True,
                    )
                    exc_dd = gr.Dropdown(
                        choices=sources,
                        value=[],
                        label="排除来源",
                        multiselect=True,
                    )
                search_toggle = gr.Checkbox(
                    value=False,
                    label="仅返回原文检索结果",
                )

        # ── Event handlers ──
        chat_inputs = [
            msg_input, chatbot, llm_state, search_toggle, src_dd, cat_dd,
            exc_dd, div_bonus, lang_bonus,
        ]
        chat_outputs = [chatbot, msg_input, llm_state]

        msg_input.submit(
            fn=_handle_chat,
            inputs=chat_inputs,
            outputs=chat_outputs,
        )
        send_button.click(
            fn=_handle_chat,
            inputs=chat_inputs,
            outputs=chat_outputs,
        )
        clear_button.click(
            fn=_clear_chat,
            outputs=chat_outputs,
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
