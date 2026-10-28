@echo off
title Virginia Legal AI - Get Everything Ready
cd /d "%~dp0"
echo.
python scripts\get_ready.py %*
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% neq 0 pause
exit /b %EXITCODE%
