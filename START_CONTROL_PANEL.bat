@echo off
REM Virginia Legal AI - Control Panel
REM Launches the desktop control panel for system management.

cd /d "%~dp0"
set PYTHONPATH=%~dp0

python scripts\control_panel.py
if errorlevel 1 pause
