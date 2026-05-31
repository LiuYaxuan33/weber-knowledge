"""Ingest pipeline: load sources -> chunk -> embed -> store.

Usage:
    python ingest.py              # Ingest all sources
    python ingest.py --force      # Delete existing data and re-ingest
    python ingest.py --stats      # Show collection stats only
"""

import sys
import time
import argparse
import config
from embeddings import create_embedding_model
from chunker import chunk_with_metadata
from store import add_sections, add_chunks, reset_collections, collection_stats
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
        sections = load_epub(path, edition, category)
    elif stype == "markdown":
        sections = load_markdown(path, edition, category)
    else:
        print(f"UNKNOWN TYPE: {stype}")
        return []

    elapsed = time.time() - t0
    print(f"{len(sections)} sections ({elapsed:.1f}s)")
    return sections


def main():
    parser = argparse.ArgumentParser(description="Ingest Weber corpus into ChromaDB")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing data and re-ingest")
    parser.add_argument("--stats", action="store_true",
                        help="Show collection stats only")
    args = parser.parse_args()

    if args.stats:
        stats = collection_stats()
        print(f"Sections: {stats['sections']}, Chunks: {stats['chunks']}")
        return

    if args.force:
        print("Resetting collections...")
        reset_collections()
    else:
        # Check if already ingested
        stats = collection_stats()
        if stats["sections"] > 0 and stats["chunks"] > 0:
            print(f"Already ingested: {stats['sections']} sections, {stats['chunks']} chunks")
            print("Use --force to re-ingest")
            return

    print("Creating embedding model...")
    embed_model = create_embedding_model()
    print(f"  Using: {config.EMBEDDING_MODEL} (dim={embed_model.dim})")

    total_chunks = 0

    for src in config.SOURCES:
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
    print(f"\nDone. Collection: {stats['sections']} sections, {stats['chunks']} chunks")


if __name__ == "__main__":
    main()
