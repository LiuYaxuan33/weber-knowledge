"""Ingest pipeline: load sources -> chunk -> embed -> store.

Usage:
    python ingest.py              # Incremental: only ingest new/unknown books
    python ingest.py --add SRC    # Force ingest one source by name (even if already present)
    python ingest.py --force      # Reset database and re-ingest everything
    python ingest.py --stats      # Show collection stats and ingested books
"""

import sys
import time
import argparse
import config
from embeddings import create_embedding_model
from chunker import chunk_with_metadata
from store import add_sections, add_chunks, reset_collections, collection_stats, get_collections, repair_source_names, delete_source
from loaders.epub import load_epub
from loaders.markdown import load_markdown


def load_source(source: dict) -> list[dict]:
    """Load a single source, returning list of sections."""
    path = source["path"]
    stype = source["type"]
    edition = source["edition"]
    category = source["category"]

    print(f"  Loading [{edition}] {source['name']}...", end=" ", flush=True)
    t0 = time.time()

    if stype == "epub":
        sections = load_epub(path, edition, category, source["name"])
    elif stype == "markdown":
        sections = load_markdown(path, edition, category, source["name"])
    else:
        print(f"UNKNOWN TYPE: {stype}")
        return []

    elapsed = time.time() - t0
    print(f"{len(sections)} sections ({elapsed:.1f}s)")
    return sections


def get_ingested_sources() -> set[str]:
    """Return set of source_name values already in the sections collection.

    Backward-compatible: if no records have source_name (old ingest), falls
    back to checking editions and mapping them to source names via config.
    """
    try:
        sec_coll, _ = get_collections()
        if sec_coll.count() == 0:
            return set()
        result = sec_coll.get(include=["metadatas"])
        sources = set()
        editions_found = set()
        has_source_name = False

        for meta in result.get("metadatas", []):
            if not meta:
                continue
            if "source_name" in meta and meta["source_name"]:
                sources.add(meta["source_name"])
                has_source_name = True
            if "edition" in meta:
                editions_found.add(meta["edition"])

        # Fallback: old data without source_name — match editions to sources
        if not has_source_name and editions_found:
            for src in config.SOURCES:
                if src["edition"] in editions_found:
                    sources.add(src["name"])

        return sources
    except Exception:
        return set()


def build_edition_source_map() -> dict[str, str]:
    """Build {edition: source_name} mapping from config."""
    mapping = {}
    for src in config.SOURCES:
        if src["edition"] not in mapping:
            mapping[src["edition"]] = src["name"]
    return mapping


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
        source_map = build_edition_source_map()
        print(f"Repairing with mapping: {source_map}")
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
        print("Resetting collections...")
        reset_collections()
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
    print(f"  Using: {config.EMBEDDING_MODEL} (dim={embed_model.dim})")

    total_chunks = 0

    for src in sources_to_ingest:
        sections = load_source(src)
        if not sections:
            continue

        # Embed sections
        print(f"    Embedding {len(sections)} sections...", end=" ", flush=True)
        t0 = time.time()
        section_texts = [s["text"] for s in sections]
        section_embs = embed_model.embed_documents(section_texts)
        for s, emb in zip(sections, section_embs):
            s["embedding"] = emb
        n_sec = add_sections(sections, embed_model)
        print(f"stored {n_sec} ({time.time() - t0:.1f}s)")

        # Chunk each section
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
        n_ch = add_chunks(src_chunks, embed_model)
        total_chunks += n_ch
        print(f"stored {n_ch} ({time.time() - t0:.1f}s)")

    # Final stats
    stats = collection_stats()
    books = get_ingested_sources()
    print(f"\nDone. Collection: {stats['sections']} sections, {stats['chunks']} chunks")
    print(f"Ingested books: {', '.join(sorted(books))}")


if __name__ == "__main__":
    main()
