#!/usr/bin/env bash
# Setup script for Weber Knowledge Base
# Run this after git clone / git pull on a new computer.
#
# Usage:
#   bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  Weber Knowledge Base — First Setup"
echo "========================================"
echo ""

# 1. Check Python and create an isolated environment
echo "[1/4] Checking Python..."
if ! command -v python &>/dev/null; then
    echo "ERROR: Python not found. Please install Python 3.10+ first."
    exit 1
fi
PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PYVER detected"
if [ ! -x ".venv/bin/python" ]; then
    python -m venv .venv
fi
PYTHON_BIN=".venv/bin/python"
echo ""

# 2. Setup .env
echo "[2/4] Setting up .env..."
if [ -f ".env" ] && grep -q "^DEEPSEEK_API_KEY=sk-" .env 2>/dev/null; then
    echo "  .env already configured, skipping"
else
    if [ ! -f ".env" ]; then
        cp .env.template .env
    fi
    echo ""
    echo "  You need a DeepSeek API key to use the LLM Q&A feature."
    echo "  Get one at: https://platform.deepseek.com/api_keys"
    echo ""
    read -r -s -p "  Enter your DEEPSEEK_API_KEY (or press Enter to skip): " WEBER_KEY
    echo ""
    if [ -n "$WEBER_KEY" ]; then
        export WEBER_SETUP_KEY="$WEBER_KEY"
        "$PYTHON_BIN" -c "import os,pathlib; p=pathlib.Path('.env'); lines=p.read_text(encoding='utf-8').splitlines(); key=os.environ['WEBER_SETUP_KEY']; p.write_text('\\n'.join(('DEEPSEEK_API_KEY='+key) if x.startswith('# DEEPSEEK_API_KEY=') or x.startswith('DEEPSEEK_API_KEY=') else x for x in lines)+'\\n',encoding='utf-8')"
        unset WEBER_SETUP_KEY WEBER_KEY
        echo "  API key saved to .env"
    else
        echo "  Skipped. You can edit .env manually later."
    fi
fi
echo ""

# 3. Install dependencies
echo "[3/4] Installing Python dependencies..."
"$PYTHON_BIN" -m pip install --upgrade pip -q
"$PYTHON_BIN" -m pip install -r requirements.txt -q
echo "  Done"
echo ""

# 4. Import vector database
echo "[4/4] Importing vector database..."
NPZ_FILE="data/weber_data.npz"

if [ -f "$NPZ_FILE" ]; then
    "$PYTHON_BIN" import_data.py
elif ls "$NPZ_FILE".part* 1>/dev/null 2>&1; then
    echo "  Found split parts, joining..."
    "$PYTHON_BIN" import_data.py
else
    echo ""
    echo "  WARNING: $NPZ_FILE not found."
    echo "  The vector database needs to be built from scratch."
    echo "  Run: python ingest.py"
    echo ""
    echo "  This requires:"
    echo "    - Source files (资料原档/)"
    echo "    - ~2GB download for the bge-m3 embedding model"
    echo "    - A GPU with 8GB+ VRAM (or CPU with 16GB+ RAM)"
    echo ""
    read -r -p "  Run ingest now? (y/N): " RUN_INGEST
    if [ "$RUN_INGEST" = "y" ] || [ "$RUN_INGEST" = "Y" ]; then
        "$PYTHON_BIN" ingest.py
    fi
fi

echo ""
echo "========================================"
echo "  Setup complete!"
echo ""
echo "  Quick start:"
echo "    .venv/bin/python app.py            # Web chat interface (Gradio)"
echo "    .venv/bin/python query.py -i       # Terminal interactive mode"
echo "    .venv/bin/python query.py \"问题\"  # Single question"
echo "========================================"
