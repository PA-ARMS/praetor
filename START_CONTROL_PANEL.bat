@echo off
title AKLAWMS - System Control Panel
cd /d "%~dp0"

echo ========================================
echo   AKLAWMS System Control Panel
echo ========================================
echo.

REM Launch the desktop control panel (requires Python)
python scripts\control_panel.py

echo.
echo Control panel closed.
pause





















