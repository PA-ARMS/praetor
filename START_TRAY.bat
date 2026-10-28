@echo off
REM Virginia Legal AI - System Tray
REM Launches the system tray icon for quick access to all GUI tools.
REM Right-click the tray icon for the menu.

cd /d "%~dp0"
set PYTHONPATH=%~dp0

python scripts\system_tray.py
if errorlevel 1 (
    echo.
    echo If pystray is not installed, run: pip install pystray
    pause
)
