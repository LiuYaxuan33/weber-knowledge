@echo off
cd /d "%~dp0weber-rag"

echo.
echo   Weber Knowledge Base
echo   --------------------
echo   Loading... browser will open shortly.
echo   If not, visit http://127.0.0.1:7860
echo.

set HF_HUB_OFFLINE=1
set PYTHONIOENCODING=utf-8

python app.py
pause
