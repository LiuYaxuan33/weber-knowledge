@echo off
cd /d "%~dp0weber-rag"
set HF_HUB_OFFLINE=1
set PYTHONIOENCODING=utf-8

echo ========================================
echo   Weber Knowledge Base
echo ========================================
echo.
echo Starting server, please wait...
echo The browser will open automatically when ready.
echo.
echo Press Ctrl+C to stop the server.
echo ========================================
echo.

C:\Users\32783\Anaconda3\python.exe app.py
pause
