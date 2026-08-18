@echo off
cd /d "%~dp0weber-rag"
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

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else if exist "C:\Users\32783\Anaconda3\python.exe" (
    "C:\Users\32783\Anaconda3\python.exe" app.py
) else (
    python app.py
)
pause
