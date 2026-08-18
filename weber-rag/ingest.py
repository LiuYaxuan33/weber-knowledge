"""Ingest pipeline: load sources -> chunk -> embed -> store.

Usage:
    python ingest.py              # Incremental: only ingest new/unknown books
    python ingest.py --add SRC    # Force ingest one source by name (even if already present)
    python ingest.py --force      # Reset database and re-ingest everything
    python ingest.py --stats      # Show collection stats and ingested books
"""

import time
import argparse
import numpy as np
import config
from embeddings import create_embedding_model
from chunker import chunk_with_metadata
from store import (add_sections, add_chunks, reset_collections, collection_stats,
                   get_collections, repair_source_names, delete_source,
                   is_non_content_chapter)
from loaders.epub import load_epub
from loaders.markdown import load_markdown
from index_manifest import build_manifest, write_manifest


def load_source(source: dict) -> list[dict]:
    """Load a single source, returning list of sections."""
    path = source["path"]
    stype = source["type"]
    publisher = source["publisher"] or ""
    category = source["category"]
    year = source.get("year")
    author = source.get("author", "")

    print(f"  Loading [{publisher}] {source['name']}...", end=" ", flush=True)
    t0 = time.time()

    if stype == "epub":
        sections = load_epub(path, publisher, category, source["name"],
                             year=year, author=author,
                             book_title=source.get("title", ""))
    elif stype == "markdown":
        sections = load_markdown(path, publisher, category, source["name"],
                                 year=year, author=author,
                                 book_title=source.get("title", ""))
    else:
        print(f"UNKNOWN TYPE: {stype}")
        return []

    elapsed = time.time() - t0
    sections = [
        section for section in sections
        if not is_non_content_chapter(section.get("metadata", {}).get("chapter", ""))
    ]
    print(f"{len(sections)} sections ({elapsed:.1f}s)")
    return sections


def get_ingested_sources() -> set[str]:
    """Return set of source_name values already in the sections collection.

    Backward-compatible: if no records have source_name (old ingest), falls
    back to checking publishers and mapping them to source names via config.
    """
    try:
        sec_coll, _ = get_collections()
        if sec_coll.count() == 0:
            return set()
        result = sec_coll.get(include=["metadatas"])
        sources = set()
        publishers_found = set()
        has_source_name = False

        for meta in result.get("metadatas", []):
            if not meta:
                continue
            if "source_name" in meta and meta["source_name"]:
                sources.add(meta["source_name"])
                has_source_name = True
            if "publisher" in meta:
                publishers_found.add(meta["publisher"])

        # Fallback: old data without source_name — match publishers to sources
        if not has_source_name and publishers_found:
            for src in config.SOURCES:
                if src["publisher"] in publishers_found:
                    sources.add(src["name"])

        return sources
    except Exception:
        return set()


def build_publisher_source_map() -> dict[str, str]:
    """Build an unambiguous {publisher: source_name} legacy mapping.

    A publisher shared by multiple books cannot identify a source and is
    deliberately omitted instead of silently assigning everything to the
    first configured book.
    """
    grouped: dict[str, list[str]] = {}
    for src in config.SOURCES:
        if src["publisher"]:
            grouped.setdefault(src["publisher"], []).append(src["name"])
    return {publisher: names[0] for publisher, names in grouped.items() if len(names) == 1}


def assign_section_embeddings(sections: list[dict], chunks: list[dict]) -> None:
    """Represent each full section by the normalized mean of all its chunks.

    Encoding a whole chapter directly truncates long chapters at the model's
    sequence limit. Pooling chunk vectors covers the complete chapter without
    an additional model pass.
    """
    grouped: dict[str, list[list[float]]] = {}
    for chunk in chunks:
        section_id = chunk["metadata"]["section_id"]
        grouped.setdefault(section_id, []).append(chunk["embedding"])

    for section in sections:
        section_id = section["metadata"]["section_id"]
        vectors = grouped.get(section_id)
        if not vectors:
            raise ValueError(f"Section has no chunk embeddings: {section_id}")
        pooled = np.asarray(vectors, dtype=np.float32).mean(axis=0)
        norm = float(np.linalg.norm(pooled))
        if norm:
            pooled /= norm
        section["embedding"] = pooled.tolist()


def main():
    parser = argparse.ArgumentParser(description="Ingest Weber corpus into ChromaDB")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing data and re-ingest everything")
    parser.add_argument("--add", type=str, metavar="SRC",
                        help="Force ingest a specific source by name (even if already present)")
    parser.add_argument("--stats", action="store_true",
                        help="Show collection stats and ingested books")
    parser.add_argument("--repair", action="store_true",
                        help="Add source_name to existing data from older ingest")
    parser.add_argument("--delete", type=str, metavar="SRC",
                        help="Delete a single source from the database by name")
    args = parser.parse_args()

    if args.delete:
        print(f"Deleting source: {args.delete}")
        n = delete_source(args.delete)
        print(f"Deleted ~{n} records for '{args.delete}'.")
        return

    if args.repair:
        source_map = build_publisher_source_map()
        print("Repairing only publishers that map to exactly one source.")
        print("Ambiguous publishers require a full rebuild and will be skipped.")
        n = repair_source_names(source_map)
        print(f"Updated {n} records with source_name.")
        return

    if args.stats:
        stats = collection_stats()
        books = get_ingested_sources()
        print(f"Sections: {stats['sections']}, Chunks: {stats['chunks']}")
        if books:
            print(f"Ingested books: {', '.join(sorted(books))}")
        else:
            print("No books ingested yet.")
        return

    if args.force:
        ingested_books = set()
    else:
        ingested_books = get_ingested_sources()
        if ingested_books:
            print(f"Already ingested: {', '.join(sorted(ingested_books))}")

    # Determine which sources to process
    sources_to_ingest = []
    for src in config.SOURCES:
        if args.add:
            # --add: only the named source, force re-ingest it
            if src["name"] == args.add:
                sources_to_ingest.append(src)
                print(f"Force re-ingesting: {src['name']}")
        elif src["name"] in ingested_books:
            print(f"  Skipping (already ingested): {src['name']}")
        else:
            sources_to_ingest.append(src)

    if not sources_to_ingest:
        print("Nothing new to ingest. Use --force to rebuild, or --add SRC to re-ingest a specific book.")
        return

    print("Creating embedding model...")
    embed_model = create_embedding_model()
    print(f"  Using: {embed_model.model_name} (dim={embed_model.dim})")

    # Do not destroy a usable index before we know the embedding model can load.
    if args.force:
        print("Resetting collections...")
        reset_collections()

    total_chunks = 0

    for src in sources_to_ingest:
        sections = load_source(src)
        if not sections:
            continue

        # Prepare all source data before replacing existing records. This keeps
        # --add recoverable when parsing or embedding fails.
        src_chunks = []
        for s in sections:
            chunks = chunk_with_metadata(s["text"], s["metadata"])
            for c in chunks:
                c["metadata"]["chunk_id"] = f"{c['metadata']['section_id']}_c{c['metadata']['chunk_index']}"
            src_chunks.extend(chunks)

        if not src_chunks:
            continue

        print(f"    Embedding {len(src_chunks)} chunks...", end=" ", flush=True)
        t0 = time.time()
        chunk_texts = [c["text"] for c in src_chunks]
        chunk_embs = embed_model.embed_documents(chunk_texts)
        for c, emb in zip(src_chunks, chunk_embs):
            c["embedding"] = emb
        assign_section_embeddings(sections, src_chunks)

        if args.add:
            removed = delete_source(src["name"])
            print(f"    Replacing {removed} existing records...")

        n_sec = add_sections(sections, embed_model)
        n_ch = add_chunks(src_chunks, embed_model)
        total_chunks += n_ch
        print(f"stored {n_sec} sections, {n_ch} chunks ({time.time() - t0:.1f}s)")

    # Final stats
    stats = collection_stats()
    write_manifest(build_manifest(embed_model, stats))
    books = get_ingested_sources()
    print(f"\nDone. Collection: {stats['sections']} sections, {stats['chunks']} chunks")
    print(f"Ingested books: {', '.join(sorted(books))}")


if __name__ == "__main__":
    main()
