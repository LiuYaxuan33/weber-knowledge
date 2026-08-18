"""Import ChromaDB data from a portable .npz file.

Usage:
    python import_data.py                        # import from data/weber_data.npz
    python import_data.py --input PATH           # import from custom path
    python import_data.py --input PATH --force    # overwrite existing data

This rebuilds the ChromaDB vector database from exported data — no
re-embedding or source files needed. Runs on CPU, no GPU required.
"""

import os
import sys
import argparse
import hashlib
import json
import time
import numpy as np
from store import reset_collections, get_collections
from index_manifest import write_manifest


def _get_dim(arr) -> int:
    """Get embedding dimension from array, handling edge cases."""
    if arr is None or len(arr) == 0:
        return 0
    return len(arr[0])


def import_data(input_path: str, force: bool = False, batch_size: int = 5000):
    """Import data from .npz and rebuild ChromaDB collections.

    Args:
        input_path: path to the .npz file
        force: if True, overwrite existing data
        batch_size: ChromaDB upsert batch size
    """
    # Check if parts need to be joined. A previous setup may have left an
    # assembled archive behind while a git pull updated only the tracked parts.
    part0 = input_path + ".part000"
    if not os.path.exists(input_path):
        if os.path.exists(part0):
            print(f"Found split parts, joining...")
            _join_parts(input_path)
        else:
            print(f"Error: {input_path} not found.")
            print("Run 'python export_data.py' first on the source machine,")
            print("or place the .npz file (or its .part* files) in the data/ directory.")
            sys.exit(1)
    elif os.path.exists(part0):
        try:
            _verify_checksum(input_path)
        except ValueError:
            print("Assembled archive is stale; rebuilding it from tracked parts...")
            _join_parts(input_path)

    _verify_checksum(input_path)
    print(f"Loading {input_path}...", end=" ", flush=True)
    t0 = time.time()
    data = np.load(input_path, allow_pickle=False)
    print(f"done ({time.time() - t0:.1f}s)")

    sec_count = int(data.get("sec_count", 0))
    chk_count = int(data.get("chk_count", 0))
    emb_dim = int(data.get("emb_dim", 0))
    required = {
        "sec_ids", "sec_embeddings", "sec_documents", "sec_metadatas",
        "chk_ids", "chk_embeddings", "chk_documents", "chk_metadatas",
        "manifest_json",
    }
    missing = sorted(required.difference(data.files))
    if missing:
        raise ValueError(f"导出文件缺少字段: {', '.join(missing)}")

    manifest = json.loads(str(data["manifest_json"].item()))
    _validate_archive(data, sec_count, chk_count, emb_dim)

    print(f"  Sections: {sec_count}, Chunks: {chk_count}, Dim: {emb_dim}")

    sec_coll, chk_coll = get_collections()

    # Check if data already exists
    existing_secs = sec_coll.count()
    existing_chks = chk_coll.count()
    if existing_secs > 0 or existing_chks > 0:
        if force:
            print(f"Overwriting existing data ({existing_secs} sections, {existing_chks} chunks)...")
            reset_collections()
            sec_coll, chk_coll = get_collections()
        else:
            print(f"Data already exists ({existing_secs} sections, {existing_chks} chunks).")
            print("Use --force to overwrite, or run ingest.py to add new sources.")
            return

    # Import sections
    if sec_count > 0:
        print(f"Importing {sec_count} sections...")
        _import_collection(
            sec_coll,
            data["sec_ids"],
            data["sec_embeddings"],
            data["sec_documents"],
            data["sec_metadatas"],
            batch_size,
        )

    # Import chunks
    if chk_count > 0:
        print(f"Importing {chk_count} chunks...")
        _import_collection(
            chk_coll,
            data["chk_ids"],
            data["chk_embeddings"],
            data["chk_documents"],
            data["chk_metadatas"],
            batch_size,
        )

    elapsed = time.time() - t0
    if sec_coll.count() != sec_count or chk_coll.count() != chk_count:
        raise RuntimeError("导入后的记录数与归档不一致，索引可能不完整。")
    write_manifest(manifest)
    print(f"\nImport complete ({elapsed:.1f}s)")
    print(f"  Sections: {sec_coll.count()}, Chunks: {chk_coll.count()}")


def _import_collection(coll, ids, embeddings, documents, metadatas, batch_size):
    """Import entries into a ChromaDB collection in batches."""
    # Convert numpy arrays to Python lists for ChromaDB
    id_list = ids.tolist() if hasattr(ids, "tolist") else list(ids)
    emb_list = embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)
    doc_list = documents.tolist() if hasattr(documents, "tolist") else list(documents)
    meta_raw = metadatas.tolist() if hasattr(metadatas, "tolist") else list(metadatas)

    for i in range(0, len(id_list), batch_size):
        end = min(i + batch_size, len(id_list))
        batch_ids = id_list[i:end]
        batch_embs = emb_list[i:end]
        batch_docs = doc_list[i:end]

        # Parse JSON metadata strings back to dicts
        batch_metas = []
        for m in meta_raw[i:end]:
            if isinstance(m, str):
                batch_metas.append(json.loads(m))
            elif isinstance(m, dict):
                batch_metas.append(dict(m))
            else:
                batch_metas.append({})

        coll.upsert(
            ids=batch_ids,
            embeddings=batch_embs,
            documents=batch_docs,
            metadatas=batch_metas,
        )

        pct = min(100, end * 100 // len(id_list))
        print(f"  {pct}% ({end}/{len(id_list)})", end="\r")
    print()


def _join_parts(input_path: str):
    """Join .part000, .part001, ... back into the original file."""
    base = input_path
    parts = []
    i = 0
    while True:
        part_path = f"{base}.part{i:03d}"
        if not os.path.exists(part_path):
            break
        parts.append(part_path)
        i += 1

    if not parts:
        return

    print(f"Joining {len(parts)} parts into {base}...")
    with open(base, "wb") as out:
        for part in parts:
            with open(part, "rb") as pf:
                out.write(pf.read())
    print(f"Joined: {os.path.getsize(base) / 1024 / 1024:.1f} MB")


def _validate_archive(data, sec_count: int, chk_count: int, emb_dim: int) -> None:
    groups = [
        ("sec", sec_count, data["sec_ids"], data["sec_embeddings"],
         data["sec_documents"], data["sec_metadatas"]),
        ("chk", chk_count, data["chk_ids"], data["chk_embeddings"],
         data["chk_documents"], data["chk_metadatas"]),
    ]
    for label, expected, ids, embeddings, documents, metadatas in groups:
        lengths = {len(ids), len(embeddings), len(documents), len(metadatas)}
        if lengths != {expected}:
            raise ValueError(f"{label} 数组长度不一致: {sorted(lengths)}，期望 {expected}")
        if expected and (embeddings.ndim != 2 or embeddings.shape[1] != emb_dim):
            raise ValueError(
                f"{label} 嵌入维度为 {getattr(embeddings, 'shape', None)}，期望 (*, {emb_dim})"
            )


def _verify_checksum(input_path: str) -> None:
    checksum_path = input_path + ".sha256"
    if not os.path.exists(checksum_path):
        raise ValueError(f"缺少校验文件: {checksum_path}")
    with open(checksum_path, "r", encoding="ascii") as file:
        expected = file.read().strip().split()[0].lower()
    digest = hashlib.sha256()
    with open(input_path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(f"数据文件 SHA-256 校验失败: expected={expected}, actual={actual}")


def main():
    parser = argparse.ArgumentParser(
        description="Import ChromaDB data from a portable .npz file"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Input path (default: weber-rag/data/weber_data.npz)",
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing ChromaDB data",
    )
    args = parser.parse_args()

    if args.input:
        input_path = args.input
    else:
        input_path = os.path.join(os.path.dirname(__file__), "data", "weber_data.npz")

    import_data(input_path, force=args.force)


if __name__ == "__main__":
    main()
