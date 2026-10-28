@echo off
title Re-enable AK Legal Vault health monitor (Administrator)
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%"

echo.
echo  Re-enables the scheduled task: AKLegalVault_Monitor
echo  (after you used STOP_BACKEND_PAUSE_MONITOR_ADMIN.bat)
echo.
echo  UAC prompt next...
echo.

set "PS1=%ROOT%\scripts\enable_vault_monitor_elevated.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath powershell.exe -Verb RunAs -WorkingDirectory '%ROOT%' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','%PS1%')"

echo.
pause
