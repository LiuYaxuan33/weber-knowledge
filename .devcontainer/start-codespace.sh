#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if pgrep -f "weber-rag/app.py.*--port 7860" >/dev/null; then
  echo "[Weber] Web app is already running."
  exit 0
fi

APP_LOG="$HOME/weber-app.log"
nohup env \
  HOST=0.0.0.0 \
  PORT=7860 \
  WEBER_NO_BROWSER=1 \
  HF_HUB_OFFLINE=1 \
  TRANSFORMERS_OFFLINE=1 \
  python weber-rag/app.py --host 0.0.0.0 --port 7860 \
  >"$APP_LOG" 2>&1 &

echo $! >"$HOME/weber-app.pid"
echo "[Weber] Web app is starting on http://localhost:7860"
echo "[Weber] Log: $APP_LOG"
