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

# 1. Check Python
echo "[1/4] Checking Python..."
if ! command -v python &>/dev/null; then
    echo "ERROR: Python not found. Please install Python 3.10+ first."
    exit 1
fi
PYVER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PYVER detected"
echo ""

# 2. Setup .env
echo "[2/4] Setting up .env..."
if [ -f ".env" ] && grep -q "sk-" .env 2>/dev/null; then
    echo "  .env already configured, skipping"
else
    if [ ! -f ".env" ]; then
        cp .env.template .env
    fi
    echo ""
    echo "  You need a DeepSeek API key to use the LLM Q&A feature."
    echo "  Get one at: https://platform.deepseek.com/api_keys"
    echo ""
    read -r -p "  Enter your DEEPSEEK_API_KEY (or press Enter to skip): " API_KEY
    if [ -n "$API_KEY" ]; then
        # Uncomment and set the key
        sed -i "s/^# DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=$API_KEY/" .env
        echo "  API key saved to .env"
    else
        echo "  Skipped. You can edit .env manually later."
    fi
fi
echo ""

# 3. Install dependencies
echo "[3/4] Installing Python dependencies..."
pip install -r requirements.txt -q
echo "  Done"
echo ""

# 4. Import vector database
echo "[4/4] Importing vector database..."
NPZ_FILE="data/weber_data.npz"

if [ -f "$NPZ_FILE" ]; then
    python import_data.py
elif ls "$NPZ_FILE".part* 1>/dev/null 2>&1; then
    echo "  Found split parts, joining..."
    python import_data.py
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
        python ingest.py
    fi
fi

echo ""
echo "========================================"
echo "  Setup complete!"
echo ""
echo "  Quick start:"
echo "    python app.py            # Web chat interface (Gradio)"
echo "    python query.py -i       # Terminal interactive mode"
echo "    python query.py \"问题\"  # Single question"
echo "========================================"
