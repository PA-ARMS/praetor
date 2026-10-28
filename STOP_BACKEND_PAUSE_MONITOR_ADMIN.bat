@echo off
title Stop servers + pause auto-recovery monitor (Administrator)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

echo.
echo  Stops processes on ports 5001, 3000, 3001 AND disables AKLegalVault_Monitor
echo  so the 3-minute health check does not restart the backend while you work.
echo.
echo  Re-enable the monitor later: RESUME_VAULT_MONITOR_ADMIN.bat (as Administrator^)
echo.
echo  UAC prompt next...
echo.

set "PS1=%ROOT%\scripts\stop_backend_elevated.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -WorkingDirectory '%ROOT%' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%PS1%','-PauseMonitorTask')"

echo.
pause
