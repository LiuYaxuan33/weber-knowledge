import os
import chromadb
from chromadb.config import Settings as ChromaSettings
import config

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=config.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collections():
    """Return (sections_collection, chunks_collection)."""
    client = _get_client()
    sections = client.get_or_create_collection(
        name="weber_sections",
        metadata={"hnsw:space": "cosine"},
    )
    chunks = client.get_or_create_collection(
        name="weber_chunks",
        metadata={"hnsw:space": "cosine"},
    )
    return sections, chunks


def reset_collections():
    """Delete and recreate both collections."""
    client = _get_client()
    for name in ["weber_sections", "weber_chunks"]:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    global _client
    _client = None


def delete_source(source_name: str) -> int:
    """Delete all sections and chunks belonging to a single source.

    Returns total number of deleted records.
    """
    sec_coll, chk_coll = get_collections()
    total = 0

    for coll in [sec_coll, chk_coll]:
        if coll.count() == 0:
            continue
        before = coll.count()
        coll.delete(where={"source_name": source_name})
        total += before - coll.count()

    return total


def add_sections(sections: list[dict], embedding_model) -> int:
    """Add section-level documents.

    Each section: {"text": str, "metadata": {"section_id": str, "book": str, ...}}
    """
    coll, _ = get_collections()
    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for i, sec in enumerate(sections):
        sid = sec["metadata"].get("section_id", f"sec_{i}")
        ids.append(sid)
        documents.append(sec["text"])
        embeddings.append(sec["embedding"])
        # ChromaDB metadata: flat dict of str/numbers only
        safe_meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                     for k, v in sec["metadata"].items()}
        metadatas.append(safe_meta)

    if ids:
        _batch_upsert(coll, ids, embeddings, documents, metadatas)
    return len(ids)


def add_chunks(chunks: list[dict], embedding_model) -> int:
    """Add paragraph-level chunks.

    Each chunk: {"text": str, "metadata": {"chunk_id": str, "section_id": str, ...}}
    """
    _, coll = get_collections()
    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for i, ch in enumerate(chunks):
        cid = ch["metadata"].get("chunk_id", f"chunk_{i}")
        ids.append(cid)
        documents.append(ch["text"])
        embeddings.append(ch["embedding"])
        safe_meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                     for k, v in ch["metadata"].items()}
        metadatas.append(safe_meta)

    if ids:
        _batch_upsert(coll, ids, embeddings, documents, metadatas)
    return len(ids)


def _batch_upsert(coll, ids, embeddings, documents, metadatas, batch_size=5000):
    """Upsert in batches to stay under ChromaDB's max batch size."""
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        coll.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )


def _build_where(source_filter: str | list[str] | None = None,
                 source_exclude: str | None = None,
                 source_exclude_list: list[str] | None = None,
                 category_filter: str | list[str] | None = None,
                 collection_filter: str | None = None,
                 collection_exclude: str | None = None,
                 extra: dict | None = None) -> dict | None:
    """Build a ChromaDB where clause from optional filters.

    Filters that accept a list use $in / $nin for OR matching.
    source_filter/exclude match against 'source_name' field.
    collection_filter/exclude match against 'source_name' field.
    source_exclude_list: multiple source_name values to exclude.
    """
    conditions = []
    if category_filter:
        if isinstance(category_filter, list):
            conditions.append({"source_category": {"$in": category_filter}})
        else:
            conditions.append({"source_category": category_filter})
    if source_filter:
        if isinstance(source_filter, list):
            conditions.append({"source_name": {"$in": source_filter}})
        else:
            conditions.append({"source_name": source_filter})
    if source_exclude:
        conditions.append({"source_name": {"$ne": source_exclude}})
    if source_exclude_list:
        for name in source_exclude_list:
            conditions.append({"source_name": {"$ne": name}})
    if collection_filter:
        conditions.append({"source_name": collection_filter})
    if collection_exclude:
        conditions.append({"source_name": {"$ne": collection_exclude}})
    if extra:
        conditions.append(extra)

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def search_sections(query_embedding: list[float], n_results: int = 4,
                    category_filter: str | list[str] | None = None,
                    source_filter: str | list[str] | None = None,
                    source_exclude: str | None = None,
                    source_exclude_list: list[str] | None = None,
                    collection_filter: str | None = None,
                    collection_exclude: str | None = None) -> list[dict]:
    """Stage 1: find top-K relevant sections."""
    coll, _ = get_collections()
    where = _build_where(source_filter=source_filter,
                         source_exclude=source_exclude,
                         source_exclude_list=source_exclude_list,
                         category_filter=category_filter,
                         collection_filter=collection_filter,
                         collection_exclude=collection_exclude)

    if coll.count() == 0:
        return []
    fetch_count = min(coll.count(), max(n_results * 4, n_results + 10))
    result = coll.query(
        query_embeddings=[query_embedding],
        n_results=fetch_count,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return _format_results(result, limit=n_results)


def search_chunks(query_embedding: list[float], section_ids: list[str],
                  n_results: int = 6, category_filter: str | list[str] | None = None,
                  source_filter: str | list[str] | None = None,
                  source_exclude: str | None = None,
                  source_exclude_list: list[str] | None = None,
                  collection_filter: str | None = None,
                  collection_exclude: str | None = None) -> list[dict]:
    """Stage 2: find top-K chunks within selected sections."""
    _, coll = get_collections()
    extra = {"section_id": {"$in": section_ids}}
    where = _build_where(source_filter=source_filter,
                         source_exclude=source_exclude,
                         source_exclude_list=source_exclude_list,
                         category_filter=category_filter,
                         collection_filter=collection_filter,
                         collection_exclude=collection_exclude,
                         extra=extra)

    if coll.count() == 0:
        return []
    fetch_count = min(coll.count(), max(n_results * 4, n_results + 10))
    result = coll.query(
        query_embeddings=[query_embedding],
        n_results=fetch_count,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return _format_results(result, limit=n_results)


def hierarchical_search(query_embedding: list[float],
                        top_sections: int = 4, top_chunks: int = 6,
                        category_filter: str | list[str] | None = None,
                        source_filter: str | list[str] | None = None,
                        source_exclude: str | None = None,
                        source_exclude_list: list[str] | None = None,
                        collection_filter: str | None = None,
                        collection_exclude: str | None = None,
                        query_text: str = "",
                        diversity_bonus: float | None = None,
                        cross_lang_bonus: float | None = None) -> tuple[list[dict], list[dict]]:
    """Two-stage hierarchical retrieval.

    Returns (section_results, chunk_results).
    Explicit scoring bonuses are request-local. Config values are defaults.
    """
    div_bonus = config.DIVERSITY_BONUS if diversity_bonus is None else diversity_bonus
    lang_bonus = config.CROSS_LANG_BONUS if cross_lang_bonus is None else cross_lang_bonus

    sections = search_sections(query_embedding, n_results=top_sections,
                               category_filter=category_filter,
                               source_filter=source_filter,
                               source_exclude=source_exclude,
                               source_exclude_list=source_exclude_list,
                               collection_filter=collection_filter,
                               collection_exclude=collection_exclude)
    if not sections:
        return [], []

    section_ids = [s["metadata"]["section_id"] for s in sections if "section_id" in s["metadata"]]
    if not section_ids:
        return sections, []

    chunks = search_chunks(query_embedding, section_ids, n_results=top_chunks,
                           category_filter=category_filter,
                           source_filter=source_filter,
                           source_exclude=source_exclude,
                           source_exclude_list=source_exclude_list,
                           collection_filter=collection_filter,
                           collection_exclude=collection_exclude)

    # Diversity bonus: boost top-1 chunk per source (book/collection)
    if div_bonus > 0:
        seen_sources = {}
        for c in chunks:
            src = c["metadata"].get("source_name", "")
            if src and src not in seen_sources:
                seen_sources[src] = True
                c["distance"] = max(0, c["distance"] - div_bonus)

    # Cross-language bonus
    if lang_bonus > 0:
        query_is_cjk = _is_cjk(query_text) if query_text else False
        for c in chunks:
            chunk_is_cjk = _is_cjk(c.get("text", "")[:200])
            if query_is_cjk != chunk_is_cjk:
                c["distance"] = max(0, c["distance"] - lang_bonus)

    chunks.sort(key=lambda c: c["distance"])

    return sections, chunks


def collection_stats() -> dict:
    """Return counts for both collections."""
    try:
        sec_coll, chk_coll = get_collections()
        return {
            "sections": sec_coll.count(),
            "chunks": chk_coll.count(),
        }
    except Exception:
        return {"sections": 0, "chunks": 0}


def list_book_names(min_chunks: int = 0) -> list[str]:
    """Return sorted unique book names from the chunks collection.

    Args:
        min_chunks: filter out books with fewer chunks than this threshold.
                    Default 0 = return all.
    """
    _, coll = get_collections()
    total = coll.count()
    if total == 0:
        return []
    counts: dict[str, int] = {}
    batch = 5000
    for offset in range(0, total, batch):
        result = coll.get(limit=batch, offset=offset, include=["metadatas"])
        for m in result.get("metadatas", []):
            if m and m.get("book"):
                book = m["book"]
                counts[book] = counts.get(book, 0) + 1
    return sorted(b for b, c in counts.items() if c >= min_chunks)


def list_sources_grouped(min_chunks: int = 0) -> list[dict]:
    """Return books grouped by parent source, with chunk counts.

    Returns list of dicts, each representing a parent source with its sub-books:
        [{"source_name": str, "publisher": str, "books": [{"book": str, "chunks": int}]}]

    Args:
        min_chunks: filter out books with fewer chunks than this threshold.
    """
    _, coll = get_collections()
    total = coll.count()
    if total == 0:
        return []
    # source_name -> {book -> {chunks, publisher}}
    groups: dict[str, dict] = {}
    batch = 5000
    for offset in range(0, total, batch):
        result = coll.get(limit=batch, offset=offset, include=["metadatas"])
        for m in result.get("metadatas", []):
            if not m or not m.get("book"):
                continue
            src = m.get("source_name", "未知来源")
            book = m["book"]
            publisher = m.get("publisher", "?")
            if src not in groups:
                groups[src] = {"publisher": publisher, "books": {}}
            if book not in groups[src]["books"]:
                groups[src]["books"][book] = 0
            groups[src]["books"][book] += 1

    # Build result, filter and sort
    output = []
    for src in sorted(groups.keys()):
        info = groups[src]
        books = [{"book": b, "chunks": c}
                 for b, c in sorted(info["books"].items(), key=lambda x: -x[1])
                 if c >= min_chunks]
        if books:
            output.append({
                "source_name": src,
                "publisher": info["publisher"],
                "books": books,
            })
    return output


def repair_source_names(source_map: dict[str, str]) -> int:
    """Add source_name to existing metadatas that lack it.

    source_map: {publisher: source_name} — built from config.SOURCES.
    Returns number of records updated.
    """
    sec_coll, chk_coll = get_collections()
    updated = 0

    for coll in [sec_coll, chk_coll]:
        if coll.count() == 0:
            continue
        result = coll.get(include=["metadatas"])
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])

        fix_ids = []
        fix_metas = []
        for id_, meta in zip(ids, metadatas):
            if meta and "source_name" not in meta:
                publisher = meta.get("publisher", "")
                if publisher in source_map:
                    new_meta = dict(meta)
                    new_meta["source_name"] = source_map[publisher]
                    fix_ids.append(id_)
                    fix_metas.append(new_meta)

        if fix_ids:
            coll.update(ids=fix_ids, metadatas=fix_metas)
            updated += len(fix_ids)

    return updated
def _format_results(result: dict, limit: int | None = None) -> list[dict]:
    """Convert ChromaDB query result to list of dicts, filtering front matter."""
    if not result["ids"] or not result["ids"][0]:
        return []

    formatted = []
    ids = result["ids"][0]
    docs = result["documents"][0] if result["documents"] else [""] * len(ids)
    metas = result["metadatas"][0] if result["metadatas"] else [{}] * len(ids)
    dists = result["distances"][0] if result["distances"] else [0] * len(ids)

    for i in range(len(ids)):
        meta = metas[i] or {}
        chapter = meta.get("chapter", "")
        if is_non_content_chapter(chapter):
            continue
        formatted.append({
            "id": ids[i],
            "text": docs[i],
            "metadata": meta,
            "distance": dists[i],
        })
        if limit is not None and len(formatted) >= limit:
            break
    return formatted


_NON_CONTENT_TITLES = {
    "目录", "版权", "版权页", "版权信息", "英文版权页", "内容简介",
    "索引", "人名索引", "文献索引", "缩略语", "缩略语列表",
    "title page", "half title page", "copyright", "copyright page",
    "contents", "frontispiece", "original copyright page", "original title page",
}


def is_non_content_chapter(chapter: str) -> bool:
    """Return True only for clearly non-substantive navigation/legal pages.

    Prefaces, notes and appendices can contain valuable scholarship and must
    remain searchable. In particular, substring matching on ``序`` would also
    remove 正当性秩序、法律程序 and 种姓阶序.
    """
    if not chapter:
        return False
    normalized = " ".join(chapter.replace("　", " ").split()).strip(" ：:.-—_")
    return normalized.lower() in _NON_CONTENT_TITLES


def _is_front_matter(chapter: str) -> bool:
    """Deprecated internal alias retained for compatibility."""
    return is_non_content_chapter(chapter)


def _is_cjk(text: str) -> bool:
    """Heuristic: does the text contain mostly CJK characters?"""
    if not text:
        return False
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    return cjk > len(text) * 0.15
