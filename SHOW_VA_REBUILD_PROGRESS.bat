@echo off
cd /d "%~dp0"
title Virginia Law Rebuild - Progress
python scripts\va_rebuild_progress_gui.py
if errorlevel 1 pause
