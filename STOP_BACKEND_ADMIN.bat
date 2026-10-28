@echo off
title Stop backend/frontend (Administrator)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

echo.
echo  This stops whatever is listening on ports 5001, 3000, 3001.
echo  Required when Python runs as SYSTEM (Session 0) from a scheduled task —
echo  a normal user cannot end that process.
echo.
echo  Also available: STOP_BACKEND_PAUSE_MONITOR_ADMIN.bat
echo    (same as above + disables the 3-min monitor so it will not auto-restart servers)
echo.
echo  You will get a UAC prompt (Administrator).
echo.

set "PS1=%ROOT%\scripts\stop_backend_elevated.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -WorkingDirectory '%ROOT%' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%PS1%')"

echo.
pause
