@echo off
REM Monitor a running build - shows live output from complete_legal_database.py
REM or verify_and_complete_database.py running in another terminal

cd /d "%~dp0"
python scripts\build_monitor.py
if errorlevel 1 pause
