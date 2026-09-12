#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[Weber] Waiting for the Python environment..."
for _ in {1..120}; do
  if python -c "import chromadb, gradio, sentence_transformers" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

if ! python -c "import chromadb, gradio, sentence_transformers" >/dev/null 2>&1; then
  echo "[Weber] Python environment did not become ready within 10 minutes."
  exit 1
fi

if pgrep -f "weber-rag/(app|serve).py" >/dev/null; then
  echo "[Weber] Web app is already running."
  exit 0
fi

APP_LOG="$HOME/weber-app.log"
nohup env \
  HOST=0.0.0.0 \
  PORT=7860 \
  WEBER_NO_BROWSER=1 \
  python weber-rag/serve.py \
  >"$APP_LOG" 2>&1 &

echo $! >"$HOME/weber-app.pid"
echo "[Weber] Web app is starting on http://localhost:7860"
echo "[Weber] Log: $APP_LOG"
