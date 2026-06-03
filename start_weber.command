#!/usr/bin/env bash
cd "$(dirname "$0")/weber-rag"
export HF_HUB_OFFLINE=1
export PYTHONIOENCODING=utf-8
open http://127.0.0.1:7860
python app.py
