"""Query interface for the Weber knowledge base.

Usage:
    python query.py "韦伯如何看待新教伦理与资本主义精神的关系？"
    python query.py --search-only "理想类型"    # retrieve only, skip LLM
    python query.py --category "韦伯著述" "什么是理想类型？"
    python query.py --source "学术与政治" "Klarheit"
    python query.py --exclude "宗教社会学" "魔鬼是个老人"
    python query.py --interactive
    python query.py --list-categories
    python query.py --list-sources
"""

import re
import sys
import os
import argparse
from difflib import get_close_matches
from openai import OpenAI
import config
from embeddings import create_embedding_model
from store import (hierarchical_search, collection_stats,
                   list_book_names, list_sources_grouped)


SYSTEM_PROMPT = """你是一位马克斯·韦伯（Max Weber）研究专家。请基于以下参考资料回答用户的问题。

回答要求：
1. 准确引用参考资料中的原文内容，不要编造
2. 如果多个来源有不同表述，请指出差异
3. 每个关键论断后标注来源，格式：[书名, 章节名, 出版社]（参考每条结果前的"书"、"章节"、"出版社"字段）
4. 如果参考资料不足以回答问题，请明确说明
5. 回答使用中文"""


def resolve_book_name(partial: str) -> str:
    """Resolve a partial source/book name via fuzzy matching against source names.

    Returns the exact source_name, or raises ValueError with suggestions.
    """
    groups = list_sources_grouped(min_chunks=0)
    candidates = [g["source_name"] for g in groups]
    if not candidates:
        raise ValueError("知识库为空，请先运行 python ingest.py")

    # 1. Exact match (case-insensitive)
    for c in candidates:
        if c.lower() == partial.lower():
            return c

    # 2. Substring match (contains)
    subs = [c for c in candidates if partial.lower() in c.lower()]
    if len(subs) == 1:
        return subs[0]
    if len(subs) > 1:
        raise ValueError(
            '来源 "' + partial + '" 匹配到多个结果：\n' +
            "\n".join("  - " + s for s in subs) +
            "\n请使用更精确的来源名。"
        )

    # 3. Fuzzy match via difflib
    fuzz = get_close_matches(partial, candidates, n=10, cutoff=0.3)
    if fuzz:
        raise ValueError(
            '未找到匹配 "' + partial + '" 的来源。\n\n可用的来源：\n' +
            "\n".join("  - " + s for s in fuzz) +
            "\n\n使用 --list-sources 查看完整列表。"
        )

    raise ValueError(
        '未找到匹配 "' + partial + '" 的来源。\n'
        '使用 --list-sources 查看全部 ' + str(len(candidates)) + ' 个来源。'
    )


def resolve_collection_name(partial: str) -> str:
    """Resolve a partial collection (source_name) via fuzzy matching.

    Returns the exact source_name, or raises ValueError with suggestions.
    """
    groups = list_sources_grouped(min_chunks=0)
    candidates = [g["source_name"] for g in groups]
    if not candidates:
        raise ValueError("知识库为空，请先运行 python ingest.py")

    # 1. Exact match (case-insensitive)
    for c in candidates:
        if c.lower() == partial.lower():
            return c

    # 2. Substring match
    subs = [c for c in candidates if partial.lower() in c.lower()]
    if len(subs) == 1:
        return subs[0]
    if len(subs) > 1:
        raise ValueError(
            '合集 "' + partial + '" 匹配到多个结果：\n' +
            "\n".join("  - " + s for s in subs) +
            "\n请使用更精确的合集名。"
        )

    # 3. Fuzzy match
    fuzz = get_close_matches(partial, candidates, n=10, cutoff=0.3)
    if fuzz:
        raise ValueError(
            '未找到匹配 "' + partial + '" 的合集。\n\n可用的合集：\n' +
            "\n".join("  - " + s for s in fuzz) +
            "\n\n使用 --list-sources 查看完整列表。"
        )

    raise ValueError(
        '未找到匹配 "' + partial + '" 的合集。\n'
        '使用 --list-sources 查看全部 ' + str(len(candidates)) + ' 个合集。'
    )


def _format_source(meta: dict) -> str:
    """Format source citation for display: 书：《title》 | 章节：chapter | 出版社：publisher."""
    book = meta.get("book", "?")
    chapter = meta.get("chapter", "?")
    pub = meta.get("publisher", meta.get("edition", "?"))
    year = meta.get("year", "")
    yr = f" {year}" if year else ""
    return f"书：《{book}》 | 章节：{chapter} | 出版社：{pub}{yr}"


def format_context(sections: list[dict], chunks: list[dict]) -> str:
    """Format retrieved sections and chunks into a prompt context."""
    parts = []

    if sections:
        parts.append("=== 相关章节 ===")
        for i, s in enumerate(sections):
            meta = s.get("metadata", {})
            src = _format_source(meta)
            text = s["text"][:5000]
            parts.append(f"\n{src}\n{text}\n")

    if chunks:
        parts.append("=== 相关段落 ===")
        for i, c in enumerate(chunks):
            meta = c.get("metadata", {})
            src = _format_source(meta)
            parts.append(f"\n--- 段落 {i+1} ---\n{src}\n{c['text']}\n")

    return "\n".join(parts)


def search_only(query: str, embed_model, category_filter: str | None = None,
                source_filter: str | None = None,
                source_exclude: str | None = None,
                collection_filter: str | None = None,
                collection_exclude: str | None = None) -> str:
    """Retrieve and display matching text without LLM Q&A."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 python ingest.py"

    q_emb = embed_model.embed_query(query)
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude=source_exclude,
        collection_filter=collection_filter,
        collection_exclude=collection_exclude,
        query_text=query,
    )

    if not sections and not chunks:
        return "未找到相关内容。"

    # Show similarity scores if available
    if sections:
        print(f"=== 相关章节 (top {len(sections)}) ===")
        for i, s in enumerate(sections):
            meta = s.get("metadata", {})
            dist = s.get("distance")
            score = f" [相似度: {1 - dist:.4f}]" if dist is not None else ""
            src = _format_source(meta)
            text = s["text"][:5000]
            print(f"\n--- 章节 {i+1}{score} ---")
            print(src)
            print(text)

    if chunks:
        print(f"\n=== 相关段落 (top {len(chunks)}) ===")
        for i, c in enumerate(chunks):
            meta = c.get("metadata", {})
            dist = c.get("distance")
            score = f" [相似度: {1 - dist:.4f}]" if dist is not None else ""
            src = _format_source(meta)
            print(f"\n--- 段落 {i+1}{score} ---")
            print(src)
            print(c["text"])

    # Summary
    sources = set()
    for item in (chunks or []) + (sections or []):
        meta = item.get("metadata", {})
        pub = meta.get("publisher", meta.get("edition", "?"))
        sources.add(f"《{meta.get('book', '?')}》（{pub}）")

    print(f"\n---\n共检索到 {len(sections)} 个章节、{len(chunks)} 个段落"
          f"（来自 {len(sources)} 个来源）")

    return ""  # Already printed directly


def answer_query(query: str, embed_model, category_filter: str | None = None,
                 source_filter: str | None = None,
                 source_exclude: str | None = None,
                 collection_filter: str | None = None,
                 collection_exclude: str | None = None) -> str:
    """Full RAG pipeline: retrieve + generate."""
    # Check if collection has data
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 python ingest.py"

    # Embed query
    q_emb = embed_model.embed_query(query)

    # Hierarchical retrieval
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude=source_exclude,
        collection_filter=collection_filter,
        collection_exclude=collection_exclude,
        query_text=query,
    )

    if not sections and not chunks:
        return "未找到相关内容。"

    # Build context
    context = format_context(sections, chunks)

    # Call LLM
    client = OpenAI(
        api_key=os.environ.get(config.LLM_API_KEY_ENV, os.environ.get("OPENAI_API_KEY")),
        base_url=config.LLM_BASE_URL,
    )
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"参考资料：\n\n{context}\n\n问题：{query}"},
        ],
    )

    answer = response.choices[0].message.content

    # Append source summary
    sources = set()
    for c in (chunks or []) + (sections or []):
        meta = c.get("metadata", {})
        book = meta.get("book", "?")
        chapter = meta.get("chapter", "?")
        pub = meta.get("publisher", meta.get("edition", "?"))
        sources.add(f"《{book}》 {chapter}（{pub}）")

    if sources:
        answer += "\n\n---\n参考来源：\n" + "\n".join(sorted(sources)[:10])

    return answer


def _get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get(config.LLM_API_KEY_ENV, os.environ.get("OPENAI_API_KEY")),
        base_url=config.LLM_BASE_URL,
    )


def answer_query_with_history(query: str, embed_model,
                               category_filter: str | None = None,
                               source_filter: str | None = None,
                               source_exclude: str | None = None,
                               collection_filter: str | None = None,
                               collection_exclude: str | None = None):
    """First question: full RAG retrieval, returns (answer, history)."""
    stats = collection_stats()
    if stats["chunks"] == 0:
        return "知识库尚未索引。请先运行 python ingest.py", []

    q_emb = embed_model.embed_query(query)
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude=source_exclude,
        collection_filter=collection_filter,
        collection_exclude=collection_exclude,
        query_text=query,
    )

    if not sections and not chunks:
        return "未找到相关内容。", []

    context = format_context(sections, chunks)
    client = _get_llm_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"参考资料：\n\n{context}\n\n问题：{query}"},
    ]

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=messages,
    )

    answer = response.choices[0].message.content
    messages.append({"role": "assistant", "content": answer})
    return answer, messages


def follow_up(query: str, history: list[dict], embed_model,
              category_filter: str | None = None,
              source_filter: str | None = None,
              source_exclude: str | None = None,
              collection_filter: str | None = None,
              collection_exclude: str | None = None):
    """Follow-up question: re-retrieve, append to history, returns (answer, history)."""
    # Re-retrieve context for the new question
    q_emb = embed_model.embed_query(query)
    sections, chunks = hierarchical_search(
        q_emb,
        top_sections=config.TOP_SECTIONS,
        top_chunks=config.TOP_CHUNKS,
        category_filter=category_filter,
        source_filter=source_filter,
        source_exclude=source_exclude,
        collection_filter=collection_filter,
        collection_exclude=collection_exclude,
        query_text=query,
    )

    context = format_context(sections, chunks)
    client = _get_llm_client()

    # Append user message with new context
    history.append({
        "role": "user",
        "content": f"参考资料：\n\n{context}\n\n追问：{query}",
    })

    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        messages=history,
    )

    answer = response.choices[0].message.content
    history.append({"role": "assistant", "content": answer})
    return answer, history


def main():
    parser = argparse.ArgumentParser(description="Query the Weber knowledge base")
    parser.add_argument("query", nargs="?", help="Search query (if not using --interactive)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode")
    parser.add_argument("--category", "-c", default=None,
                        choices=config.CATEGORIES,
                        help="Filter by source category")
    parser.add_argument("--source", "-s", default=None,
                        help="Filter by book name (fuzzy match)")
    parser.add_argument("--exclude", "-e", default=None,
                        help="Exclude a book by name (fuzzy match)")
    parser.add_argument("--collection", "-C", default=None,
                        help="Filter by parent collection (fuzzy match)")
    parser.add_argument("--exclude-collection", "-E", default=None,
                        help="Exclude a parent collection (fuzzy match)")
    parser.add_argument("--list-categories", action="store_true",
                        help="List available categories and exit")
    parser.add_argument("--list-sources", action="store_true",
                        help="List available book names and exit")
    parser.add_argument("--show-all", action="store_true",
                        help="With --list-sources: include small entries (front/back matter)")
    parser.add_argument("--top-sections", type=int, default=config.TOP_SECTIONS,
                        help=f"Number of top sections (default: {config.TOP_SECTIONS})")
    parser.add_argument("--top-chunks", type=int, default=config.TOP_CHUNKS,
                        help=f"Number of top chunks (default: {config.TOP_CHUNKS})")
    parser.add_argument("--search-only", "-S", action="store_true",
                        help="Only retrieve and print matching text, skip LLM Q&A")
    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for c in config.CATEGORIES:
            print(f"  - {c}")
        stats = collection_stats()
        print(f"\nIndexed: {stats['sections']} sections, {stats['chunks']} chunks")
        return

    if args.list_sources:
        min_c = 0 if args.show_all else 30
        groups = list_sources_grouped(min_chunks=min_c)
        for g in groups:
            print(f"\n{g['source_name']}  [{g['publisher']}]")
            for b in g["books"]:
                print(f"  {b['book']}  ({b['chunks']} 段)")
        print(f"\n共 {sum(len(g['books']) for g in groups)} 个章节" +
              f"（来自 {len(groups)} 个来源）")
        if not args.show_all:
            print("提示: 使用 --list-sources --show-all 查看包含前后附页的完整列表")
        return

    # Resolve filter names to exact values
    source_filter = None
    source_exclude = None
    collection_filter = None
    collection_exclude = None
    try:
        if args.source:
            source_filter = resolve_book_name(args.source)
        if args.exclude:
            source_exclude = resolve_book_name(args.exclude)
        if args.collection:
            collection_filter = resolve_collection_name(args.collection)
        if args.exclude_collection:
            collection_exclude = resolve_collection_name(args.exclude_collection)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"Loading embedding model ({config.EMBEDDING_MODEL})...", file=sys.stderr)
    embed_model = create_embedding_model()

    if args.interactive:
        # Mutable filter state (changeable mid-session via /slash commands)
        cat_filter = args.category
        src_filter = source_filter
        exc_filter = source_exclude
        col_filter = collection_filter
        col_exc = collection_exclude

        def _show_filters():
            parts = []
            if cat_filter:
                parts.append(f"类别: {cat_filter}")
            if col_filter:
                parts.append(f"合集: {col_filter}")
            if col_exc:
                parts.append(f"排除合集: {col_exc}")
            if src_filter:
                parts.append(f"书: {src_filter}")
            if exc_filter:
                parts.append(f"排除书: {exc_filter}")
            print(f"过滤: {', '.join(parts) if parts else '无'}", file=sys.stderr)

        def _handle_slash(cmd: str) -> bool:
            """Handle a slash command. Returns True if the command was consumed."""
            nonlocal cat_filter, src_filter, exc_filter, col_filter, col_exc, history, search_mode
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if action == "/filters":
                _show_filters()
                print(f"（检索模式: {'仅搜索' if search_mode else '搜索+问答'}）", file=sys.stderr)
                return True

            if action == "/search":
                search_mode = not search_mode
                print(f"（检索模式: {'仅搜索' if search_mode else '搜索+问答'}）", file=sys.stderr)
                return True

            if action == "/source" or action == "/s":
                if not arg:
                    print("用法: /source <来源名>  （模糊匹配）", file=sys.stderr)
                    return True
                try:
                    src_filter = resolve_book_name(arg)
                    history = []
                    print(f"（书已设为: {src_filter}，对话已重置）", file=sys.stderr)
                except ValueError as e:
                    print(str(e), file=sys.stderr)
                return True

            if action == "/exclude" or action == "/e":
                if not arg:
                    print("用法: /exclude <来源名>  （模糊匹配）", file=sys.stderr)
                    return True
                try:
                    exc_filter = resolve_book_name(arg)
                    history = []
                    print(f"（排除书已设为: {exc_filter}，对话已重置）", file=sys.stderr)
                except ValueError as e:
                    print(str(e), file=sys.stderr)
                return True

            if action == "/collection" or action == "/col":
                if not arg:
                    print("用法: /collection <合集名>  （模糊匹配）", file=sys.stderr)
                    return True
                try:
                    col_filter = resolve_collection_name(arg)
                    history = []
                    print(f"（合集已设为: {col_filter}，对话已重置）", file=sys.stderr)
                except ValueError as e:
                    print(str(e), file=sys.stderr)
                return True

            if action == "/exclude-collection" or action == "/ecol":
                if not arg:
                    print("用法: /exclude-collection <合集名>", file=sys.stderr)
                    return True
                try:
                    col_exc = resolve_collection_name(arg)
                    history = []
                    print(f"（排除合集已设为: {col_exc}，对话已重置）", file=sys.stderr)
                except ValueError as e:
                    print(str(e), file=sys.stderr)
                return True

            if action == "/category" or action == "/c":
                if not arg:
                    print(f"用法: /category <分类>  可选: {', '.join(config.CATEGORIES)}", file=sys.stderr)
                    return True
                if arg not in config.CATEGORIES:
                    print(f"未知分类。可选: {', '.join(config.CATEGORIES)}", file=sys.stderr)
                    return True
                cat_filter = arg
                history = []
                print(f"（分类已设为: {cat_filter}，对话已重置）", file=sys.stderr)
                return True

            if action == "/filter":
                sub = arg.lower()
                if sub in ("off", "clear", "none", "reset"):
                    cat_filter = None
                    src_filter = None
                    exc_filter = None
                    col_filter = None
                    col_exc = None
                    history = []
                    print("（所有过滤已关闭，对话已重置）", file=sys.stderr)
                else:
                    print("用法: /filter off  关闭所有过滤", file=sys.stderr)
                return True

            return False  # not a slash command

        print("Weber 知识库查询（输入 quit 退出，输入 /new 开始新话题）", file=sys.stderr)
        _show_filters()
        print("命令: /source /exclude /collection /category /filter /filters /new /search", file=sys.stderr)
        print(file=sys.stderr)

        history = []  # conversation messages for LLM
        search_mode = args.search_only  # True = only retrieve, skip LLM

        while True:
            try:
                query = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not query:
                continue
            if query.lower() in ("quit", "exit", "q"):
                break
            if query.lower() in ("/new", "/clear"):
                history = []
                print("（已开始新话题）", file=sys.stderr)
                print()
                continue

            # Slash commands
            if query.startswith("/"):
                if _handle_slash(query):
                    print()
                else:
                    print(f"未知命令: {query}", file=sys.stderr)
                continue

            print(file=sys.stderr)

            if search_mode:
                # Search only: retrieve and print, no LLM, no history
                search_only(query, embed_model, cat_filter,
                            source_filter=src_filter,
                            source_exclude=exc_filter,
                            collection_filter=col_filter,
                            collection_exclude=col_exc)
                print()
                continue
            elif not history:
                answer, history = answer_query_with_history(
                    query, embed_model, cat_filter,
                    source_filter=src_filter,
                    source_exclude=exc_filter,
                    collection_filter=col_filter,
                    collection_exclude=col_exc)
            else:
                answer, history = follow_up(query, history, embed_model,
                                            cat_filter,
                                            source_filter=src_filter,
                                            source_exclude=exc_filter,
                                            collection_filter=col_filter,
                                            collection_exclude=col_exc)

            print(answer)
            print()
    else:
        if not args.query:
            parser.print_help()
            return

        if args.search_only:
            search_only(args.query, embed_model, args.category,
                        source_filter=source_filter,
                        source_exclude=source_exclude,
                        collection_filter=collection_filter,
                        collection_exclude=collection_exclude)
        else:
            answer = answer_query(args.query, embed_model, args.category,
                                  source_filter=source_filter,
                                  source_exclude=source_exclude,
                                  collection_filter=collection_filter,
                                  collection_exclude=collection_exclude)
            print(answer)


if __name__ == "__main__":
    main()
