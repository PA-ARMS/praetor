@echo off
title Restart backend (Administrator)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  Restarts the API on port 5001: stops whatever is listening, then opens a new CMD running uvicorn.
echo  Approve the UAC prompt (Administrator).
echo.

set "PS1=%ROOT%\scripts\restart_backend_elevated.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -WorkingDirectory '%ROOT%' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%PS1%')"

echo.
echo  If a UAC window appeared, approve it. The backend will start in a new command window.
pause
