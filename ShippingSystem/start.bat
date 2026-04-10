@echo off
title ShipDesk - Shipping System
echo.
echo  ==============================
echo   ShipDesk - Starting up...
echo  ==============================
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo  First-time setup: creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo  ERROR: Python not found. Please install Python 3.11 or newer
        echo  from https://python.org and try again.
        pause
        exit /b 1
    )
    echo  Installing required packages (this takes a minute on first run)...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet
    echo  Setup complete!
    echo.
) else (
    call venv\Scripts\activate.bat
)

:: Start Flask in background and open browser
echo  Starting ShipDesk...
start "" /B python app.py

:: Wait a moment then open browser
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5000

echo  ShipDesk is running!
echo  Open your browser to: http://127.0.0.1:5000
echo.
echo  Keep this window open while using ShipDesk.
echo  Close this window (or press Ctrl+C) to shut down.
echo.

:: Keep window open and show Flask output
python app.py
pause
