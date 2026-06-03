"""Export ChromaDB collections to a portable compressed file.

Usage:
    python export_data.py                  # export to data/weber_data.npz
    python export_data.py --output PATH   # custom output path
    python export_data.py --split 50      # split into 50MB parts for git

The output .npz contains everything needed to rebuild the vector database
on another computer — no re-embedding or source files required.
"""

import os
import sys
import argparse
import numpy as np
import json
import time
from store import get_collections


def _read_collection(coll, name: str, batch_size: int = 5000) -> dict:
    """Read all entries from a ChromaDB collection in batches.

    Returns dict with keys: ids, embeddings, documents, metadatas
    """
    total = coll.count()
    if total == 0:
        print(f"  {name}: empty, skipping")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": []}

    print(f"  {name}: reading {total} entries...", end=" ", flush=True)

    all_ids = []
    all_embeddings = []
    all_docs = []
    all_metas = []

    for offset in range(0, total, batch_size):
        limit = min(batch_size, total - offset)
        result = coll.get(
            limit=limit,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        all_ids.extend(result.get("ids", []))
        all_embeddings.extend(result.get("embeddings", []))
        all_docs.extend(result.get("documents", []))
        all_metas.extend(result.get("metadatas", []))

    # Convert metadata to JSON strings for safe numpy storage
    meta_strs = [json.dumps(m or {}, ensure_ascii=False) for m in all_metas]

    print(f"done ({len(all_ids)} entries)")

    return {
        "ids": np.array(all_ids, dtype=object),
        "embeddings": np.array(all_embeddings, dtype=np.float32),
        "documents": np.array(all_docs, dtype=object),
        "metadatas": np.array(meta_strs, dtype=object),
    }


def export_data(output_path: str, split_mb: int = 0):
    """Export all ChromaDB data to a compressed .npz file.

    Args:
        output_path: path to write the .npz file
        split_mb: if > 0, also create split files of this many MB each
    """
    sec_coll, chk_coll = get_collections()

    print("Exporting ChromaDB collections...")
    t0 = time.time()

    sections = _read_collection(sec_coll, "weber_sections")
    chunks = _read_collection(chk_coll, "weber_chunks")

    # Compute stats
    sec_count = len(sections["ids"])
    chk_count = len(chunks["ids"])
    emb_dim = sections["embeddings"].shape[1] if sec_count > 0 else (
        chunks["embeddings"].shape[1] if chk_count > 0 else 0
    )

    print(f"\nSaving to {output_path}...", end=" ", flush=True)
    np.savez_compressed(
        output_path,
        # Section data
        sec_ids=sections["ids"],
        sec_embeddings=sections["embeddings"],
        sec_documents=sections["documents"],
        sec_metadatas=sections["metadatas"],
        # Chunk data
        chk_ids=chunks["ids"],
        chk_embeddings=chunks["embeddings"],
        chk_documents=chunks["documents"],
        chk_metadatas=chunks["metadatas"],
        # Metadata
        emb_dim=emb_dim,
        sec_count=sec_count,
        chk_count=chk_count,
    )

    file_size = os.path.getsize(output_path)
    elapsed = time.time() - t0
    print(f"done ({file_size / 1024 / 1024:.1f} MB, {elapsed:.1f}s)")

    print(f"\nExported: {sec_count} sections, {chk_count} chunks, dim={emb_dim}")

    if split_mb > 0:
        _split_file(output_path, split_mb)


def _split_file(filepath: str, chunk_mb: int):
    """Split a file into chunk_mb-sized parts for git."""
    chunk_size = chunk_mb * 1024 * 1024
    file_size = os.path.getsize(filepath)
    parts = (file_size + chunk_size - 1) // chunk_size

    print(f"\nSplitting into {parts} parts ({chunk_mb} MB each)...")

    with open(filepath, "rb") as f:
        for i in range(parts):
            part_path = f"{filepath}.part{i:03d}"
            data = f.read(chunk_size)
            with open(part_path, "wb") as pf:
                pf.write(data)
            print(f"  {part_path} ({len(data) / 1024 / 1024:.1f} MB)")

    print(f"\nTo reassemble: copy /b {filepath}.part* {filepath}   (Windows)")
    print(f"               cat {filepath}.part* > {filepath}        (Mac/Linux)")


def main():
    parser = argparse.ArgumentParser(
        description="Export ChromaDB data to a portable compressed file"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output path (default: weber-rag/data/weber_data.npz)",
    )
    parser.add_argument(
        "--split", type=int, default=0, metavar="MB",
        help="Split output into parts of N MB each (for git)",
    )
    args = parser.parse_args()

    if args.output:
        output = args.output
    else:
        output = os.path.join(os.path.dirname(__file__), "data", "weber_data.npz")

    export_data(output, split_mb=args.split)


if __name__ == "__main__":
    main()
