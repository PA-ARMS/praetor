@echo off
REM Launch the Ingestion Progress GUI
REM Shows real-time progress of the legal database build

cd /d "%~dp0"
python scripts\ingest_progress_gui.py
if errorlevel 1 pause
