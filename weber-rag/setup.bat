@echo off
REM Setup script for Weber Knowledge Base (Windows)
REM Run this after git clone / git pull on a new computer.
REM
REM Usage: setup.bat

echo ========================================
echo   Weber Knowledge Base — First Setup
echo ========================================
echo.

REM 1. Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+ first.
    pause
    exit /b 1
)
python --version
echo.

REM 2. Setup .env
echo [2/4] Setting up .env...
if exist .env (
    findstr /c:"sk-" .env >nul 2>&1
    if %errorlevel% equ 0 (
        echo   .env already configured, skipping
        goto :deps
    )
)
if not exist .env copy .env.template .env >nul
echo.
echo   You need a DeepSeek API key to use the LLM Q&A feature.
echo   Get one at: https://platform.deepseek.com/api_keys
echo.
set /p API_KEY="  Enter your DEEPSEEK_API_KEY (or press Enter to skip): "
if not "%API_KEY%"=="" (
    powershell -Command "(Get-Content .env) -replace '^# DEEPSEEK_API_KEY=.*', 'DEEPSEEK_API_KEY=%API_KEY%' | Set-Content .env"
    echo   API key saved to .env
) else (
    echo   Skipped. You can edit .env manually later.
)

:deps
echo.

REM 3. Install dependencies
echo [3/4] Installing Python dependencies...
pip install -r requirements.txt -q
echo   Done
echo.

REM 4. Import vector database
echo [4/4] Importing vector database...
set NPZ_FILE=data\weber_data.npz

if exist "%NPZ_FILE%" (
    python import_data.py
    goto :done
)
if exist "%NPZ_FILE%.part000" (
    echo   Found split parts, joining...
    python import_data.py
    goto :done
)

echo.
echo   WARNING: %NPZ_FILE% not found.
echo   The vector database needs to be built from scratch.
echo   Run: python ingest.py
echo.
echo   This requires:
echo     - Source files (资料原档/)
echo     - ~2GB download for the bge-m3 embedding model
echo     - A GPU with 8GB+ VRAM (or CPU with 16GB+ RAM)
echo.
set /p RUN_INGEST="  Run ingest now? (y/N): "
if /i "%RUN_INGEST%"=="y" python ingest.py

:done
echo.
echo ========================================
echo   Setup complete!
echo.
echo   Quick start:
echo     python app.py            Web chat interface (Gradio^)
echo     python query.py -i       Terminal interactive mode
echo     python query.py "问题"   Single question
echo ========================================
pause
