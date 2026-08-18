#!/usr/bin/env bash
cd "$(dirname "$0")/weber-rag"
export PYTHONIOENCODING=utf-8
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python app.py
else
  exec python app.py
fi
