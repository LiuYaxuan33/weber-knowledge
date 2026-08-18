@echo off
REM Setup script for Weber Knowledge Base (Windows)
REM Run this after git clone / git pull on a new computer.
REM
REM Usage: setup.bat

echo ========================================
echo   Weber Knowledge Base — First Setup
echo ========================================
echo.

REM 1. Check Python and create an isolated environment
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+ first.
    pause
    exit /b 1
)
python --version
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Failed to create .venv
    pause
    exit /b 1
)
set "PYTHON_BIN=.venv\Scripts\python.exe"
echo.

REM 2. Setup .env
echo [2/4] Setting up .env...
if exist .env (
    findstr /b /c:"DEEPSEEK_API_KEY=sk-" .env >nul 2>&1
    if not errorlevel 1 (
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
    set "WEBER_SETUP_KEY=%API_KEY%"
    "%PYTHON_BIN%" -c "import os,pathlib; p=pathlib.Path('.env'); lines=p.read_text(encoding='utf-8').splitlines(); key=os.environ['WEBER_SETUP_KEY']; p.write_text('\n'.join(('DEEPSEEK_API_KEY='+key) if x.startswith('# DEEPSEEK_API_KEY=') or x.startswith('DEEPSEEK_API_KEY=') else x for x in lines)+'\n',encoding='utf-8')"
    set "WEBER_SETUP_KEY="
    set "API_KEY="
    echo   API key saved to .env
) else (
    echo   Skipped. You can edit .env manually later.
)

:deps
echo.

REM 3. Install dependencies
echo [3/4] Installing Python dependencies...
"%PYTHON_BIN%" -m pip install --upgrade pip -q
"%PYTHON_BIN%" -m pip install -r requirements.txt -q
if %errorlevel% neq 0 exit /b 1
echo   Done
echo.

REM 4. Import vector database
echo [4/4] Importing vector database...
set NPZ_FILE=data\weber_data.npz

if exist "%NPZ_FILE%" (
    "%PYTHON_BIN%" import_data.py
    goto :done
)
if exist "%NPZ_FILE%.part000" (
    echo   Found split parts, joining...
    "%PYTHON_BIN%" import_data.py
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
if /i "%RUN_INGEST%"=="y" "%PYTHON_BIN%" ingest.py

:done
echo.
echo ========================================
echo   Setup complete!
echo.
echo   Quick start:
echo     .venv\Scripts\python.exe app.py            Web chat interface (Gradio^)
echo     .venv\Scripts\python.exe query.py -i       Terminal interactive mode
echo     .venv\Scripts\python.exe query.py "问题"   Single question
echo ========================================
pause
