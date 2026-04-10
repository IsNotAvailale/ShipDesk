@echo off
title ShipDesk
cd /d %~dp0
echo ShipDesk starting... > start_log.txt
echo Folder: %cd% >> start_log.txt
python --version >> start_log.txt 2>&1
if errorlevel 1 (
    echo ERROR: Python not installed >> start_log.txt
    echo Python is not installed on this computer.
    echo Please install Python from https://python.org
    echo Make sure to check ADD TO PATH during install.
    pause
    exit /b 1
)
echo Python OK >> start_log.txt
if not exist venv\Scripts\activate.bat (
    echo Installing packages - this takes 1-2 minutes, please wait...
    python -m venv venv >> start_log.txt 2>&1
    if errorlevel 1 (
        echo ERROR: venv creation failed >> start_log.txt
        echo Setup failed. See start_log.txt for details.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    pip install -r requirements.txt >> start_log.txt 2>&1
    echo Packages installed >> start_log.txt
) else (
    call venv\Scripts\activate.bat
)
echo Launching app... >> start_log.txt
echo ShipDesk is starting - please wait...
start "" /B python app.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:5000
echo.
echo ShipDesk is running at http://127.0.0.1:5000
echo Keep this window open. Close it to shut down.
echo.
python app.py
pause
