"""Versioned metadata describing the vector index and its embedding space."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

import config


class IndexCompatibilityError(RuntimeError):
    """Raised when the configured embedding model does not match the index."""


def _source_registry_digest() -> str:
    portable_sources = [
        {
            key: source.get(key)
            for key in ("name", "type", "category", "author", "title", "publisher", "year")
        }
        for source in config.SOURCES
    ]
    payload = json.dumps(
        portable_sources, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_manifest(embedding_model, stats: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": config.INDEX_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": embedding_model.model_name,
        "embedding_dimension": int(embedding_model.dim),
        "section_embedding_strategy": "normalized_mean_of_chunk_embeddings",
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "sections": int(stats.get("sections", 0)),
        "chunks": int(stats.get("chunks", 0)),
        "source_count": len(config.SOURCES),
        "source_registry_sha256": _source_registry_digest(),
    }


def write_manifest(manifest: dict[str, Any], path: str | None = None) -> None:
    target = path or config.INDEX_MANIFEST_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temp = target + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")
    os.replace(temp, target)


def load_manifest(path: str | None = None) -> dict[str, Any] | None:
    target = path or config.INDEX_MANIFEST_PATH
    if not os.path.exists(target):
        return None
    with open(target, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise IndexCompatibilityError("索引清单格式无效，请重新导入或重建索引。")
    return data


def validate_index_compatibility(embedding_model) -> dict[str, Any]:
    manifest = load_manifest()
    if manifest is None:
        raise IndexCompatibilityError(
            "当前向量库缺少 index_manifest.json，无法确认嵌入空间。"
            "请运行 python import_data.py --force 或 python ingest.py --force。"
        )

    schema = int(manifest.get("schema_version", 0))
    if schema != config.INDEX_SCHEMA_VERSION:
        raise IndexCompatibilityError(
            f"索引格式版本为 {schema}，程序要求 {config.INDEX_SCHEMA_VERSION}；请重新构建索引。"
        )

    indexed_model = str(manifest.get("embedding_model", ""))
    indexed_dim = int(manifest.get("embedding_dimension", 0))
    if indexed_model != embedding_model.model_name or indexed_dim != int(embedding_model.dim):
        raise IndexCompatibilityError(
            "嵌入模型与现有索引不匹配："
            f"索引={indexed_model} ({indexed_dim}维)，"
            f"当前={embedding_model.model_name} ({embedding_model.dim}维)。"
            "请恢复原模型配置或重建索引。"
        )

    if manifest.get("source_registry_sha256") != _source_registry_digest():
        raise IndexCompatibilityError(
            "config.py 的来源清单已变化，但索引尚未更新；请运行 ingest.py。"
        )
    if (
        int(manifest.get("chunk_size", 0)) != config.CHUNK_SIZE
        or int(manifest.get("chunk_overlap", 0)) != config.CHUNK_OVERLAP
    ):
        raise IndexCompatibilityError("分块配置与现有索引不匹配，请重新构建索引。")
    return manifest
