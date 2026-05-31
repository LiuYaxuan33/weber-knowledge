"""Query interface for the Weber knowledge base.

Usage:
    python query.py "韦伯如何看待新教伦理与资本主义精神的关系？"
    python query.py --category "韦伯著述" "什么是理想类型？"
    python query.py --interactive
    python query.py --list-categories
"""

import sys
import os
import argparse
from openai import OpenAI
import config
from embeddings import create_embedding_model
from store import hierarchical_search, collection_stats


SYSTEM_PROMPT = """你是一位马克斯·韦伯（Max Weber）研究专家。请基于以下参考资料回答用户的问题。

回答要求：
1. 准确引用参考资料中的原文内容，不要编造
2. 如果多个来源有不同表述，请指出差异
3. 每个关键论断后标注来源，格式：[书名, 章节名, 版本]
4. 如果参考资料不足以回答问题，请明确说明
5. 回答使用中文"""


def format_context(sections: list[dict], chunks: list[dict]) -> str:
    """Format retrieved sections and chunks into a prompt context."""
    parts = []

    if sections:
        parts.append("=== 相关章节 ===")
        for i, s in enumerate(sections):
            meta = s.get("metadata", {})
            src = f"[{meta.get('book', '?')}, {meta.get('chapter', '?')}, {meta.get('edition', '?')}版]"
            text = s["text"][:1500]  # Truncate long sections
            parts.append(f"\n{src}\n{text}\n")

    if chunks:
        parts.append("=== 相关段落 ===")
        for i, c in enumerate(chunks):
            meta = c.get("metadata", {})
            src = f"[{meta.get('book', '?')}, {meta.get('chapter', '?')}, {meta.get('edition', '?')}版]"
            parts.append(f"\n--- 段落 {i+1} {src} ---\n{c['text']}\n")

    return "\n".join(parts)


def answer_query(query: str, embed_model, category_filter: str | None = None) -> str:
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
        edition = meta.get("edition", "?")
        sources.add(f"[{book}, {chapter}, {edition}版]")

    if sources:
        answer += "\n\n---\n参考来源：\n" + "\n".join(sorted(sources)[:10])

    return answer


def main():
    parser = argparse.ArgumentParser(description="Query the Weber knowledge base")
    parser.add_argument("query", nargs="?", help="Search query (if not using --interactive)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode")
    parser.add_argument("--category", "-c", default=None,
                        choices=config.CATEGORIES,
                        help="Filter by source category")
    parser.add_argument("--list-categories", action="store_true",
                        help="List available categories and exit")
    parser.add_argument("--top-sections", type=int, default=config.TOP_SECTIONS,
                        help=f"Number of top sections (default: {config.TOP_SECTIONS})")
    parser.add_argument("--top-chunks", type=int, default=config.TOP_CHUNKS,
                        help=f"Number of top chunks (default: {config.TOP_CHUNKS})")
    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for c in config.CATEGORIES:
            print(f"  - {c}")
        stats = collection_stats()
        print(f"\nIndexed: {stats['sections']} sections, {stats['chunks']} chunks")
        return

    print(f"Loading embedding model ({config.EMBEDDING_MODEL})...", file=sys.stderr)
    embed_model = create_embedding_model()

    if args.interactive:
        print("Weber 知识库查询（输入 quit 退出）", file=sys.stderr)
        print(f"来源过滤: {args.category or '全部'}", file=sys.stderr)
        print(file=sys.stderr)

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

            print(file=sys.stderr)
            answer = answer_query(query, embed_model, args.category)
            print(answer)
            print()
    else:
        if not args.query:
            parser.print_help()
            return

        answer = answer_query(args.query, embed_model, args.category)
        print(answer)


if __name__ == "__main__":
    main()
