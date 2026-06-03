@echo off
cd /d "%~dp0weber-rag"
set HF_HUB_OFFLINE=1
set PYTHONIOENCODING=utf-8
start http://127.0.0.1:7860
python app.py
