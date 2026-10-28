@echo off
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo  Schedule Annual Virginia Law Corpus Update
echo  ==========================================
echo.
echo  Creates a Windows task to refresh VA Code every July 15 at 2:00 AM.
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\setup_va_law_update_task.ps1"
pause
