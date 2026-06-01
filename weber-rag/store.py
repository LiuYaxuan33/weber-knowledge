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

    # Try source_name first (new data), then fall back to edition field
    for coll in [sec_coll, chk_coll]:
        if coll.count() == 0:
            continue
        # Check which field exists in metadata
        sample = coll.get(limit=1, include=["metadatas"])
        metas = sample.get("metadatas", [])
        if metas and metas[0] and "source_name" in metas[0]:
            coll.delete(where={"source_name": source_name})
        elif metas and metas[0] and "edition" in metas[0]:
            coll.delete(where={"edition": source_name})
        total += coll.count()  # approximate after delete

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


def search_sections(query_embedding: list[float], n_results: int = 4,
                    category_filter: str | None = None) -> list[dict]:
    """Stage 1: find top-K relevant sections."""
    coll, _ = get_collections()
    where = None
    if category_filter:
        where = {"source_category": category_filter}

    result = coll.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return _format_results(result)


def search_chunks(query_embedding: list[float], section_ids: list[str],
                  n_results: int = 6, category_filter: str | None = None) -> list[dict]:
    """Stage 2: find top-K chunks within selected sections."""
    _, coll = get_collections()
    where = {"section_id": {"$in": section_ids}}
    if category_filter:
        where["source_category"] = category_filter

    result = coll.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return _format_results(result)


def hierarchical_search(query_embedding: list[float],
                        top_sections: int = 4, top_chunks: int = 6,
                        category_filter: str | None = None) -> tuple[list[dict], list[dict]]:
    """Two-stage hierarchical retrieval.

    Returns (section_results, chunk_results).
    """
    sections = search_sections(query_embedding, n_results=top_sections,
                               category_filter=category_filter)
    if not sections:
        return [], []

    section_ids = [s["metadata"]["section_id"] for s in sections if "section_id" in s["metadata"]]
    if not section_ids:
        return sections, []

    chunks = search_chunks(query_embedding, section_ids, n_results=top_chunks,
                           category_filter=category_filter)
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


def repair_source_names(source_map: dict[str, str]) -> int:
    """Add source_name to existing metadatas that lack it.

    source_map: {edition: source_name} — built from config.SOURCES.
    Returns number of records updated.
    """
    sec_coll, chk_coll = get_collections()
    updated = 0

    for coll, name in [(sec_coll, "sections"), (chk_coll, "chunks")]:
        if coll.count() == 0:
            continue
        result = coll.get(include=["metadatas"])
        ids = result.get("ids", [])
        metadatas = result.get("metadatas", [])

        fix_ids = []
        fix_metas = []
        for id_, meta in zip(ids, metadatas):
            if meta and "source_name" not in meta:
                edition = meta.get("edition", "")
                if edition in source_map:
                    new_meta = dict(meta)
                    new_meta["source_name"] = source_map[edition]
                    fix_ids.append(id_)
                    fix_metas.append(new_meta)

        if fix_ids:
            # We need to upsert with all required fields
            coll.update(ids=fix_ids, metadatas=fix_metas)
            updated += len(fix_ids)

    return updated
def _format_results(result: dict) -> list[dict]:
    """Convert ChromaDB query result to list of dicts."""
    if not result["ids"] or not result["ids"][0]:
        return []

    formatted = []
    ids = result["ids"][0]
    docs = result["documents"][0] if result["documents"] else [""] * len(ids)
    metas = result["metadatas"][0] if result["metadatas"] else [{}] * len(ids)
    dists = result["distances"][0] if result["distances"] else [0] * len(ids)

    for i in range(len(ids)):
        formatted.append({
            "id": ids[i],
            "text": docs[i],
            "metadata": metas[i],
            "distance": dists[i],
        })
    return formatted
