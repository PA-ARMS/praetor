@echo off
title Virginia Legal AI - Verify Everything
cd /d "%~dp0"
echo.
python scripts\verify_everything.py %*
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% neq 0 pause
exit /b %EXITCODE%
