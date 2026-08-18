#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[Weber] Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[Weber] Restoring the portable vector index..."
python weber-rag/import_data.py

echo "[Weber] Downloading and validating BGE-M3..."
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3', device='cpu'); print('[Weber] BGE-M3 ready.')"

echo "[Weber] Codespace setup complete."
