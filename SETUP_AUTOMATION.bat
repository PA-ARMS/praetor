@echo off
cd /d "%~dp0"

:: Request Administrator if not already elevated
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo  AK Legal Vault - Setup Automated Operation
echo  ==========================================
echo.
echo  This will configure:
echo    - Start when Windows boots (if PC is on, system is on)
echo    - Restart every night at midnight
echo    - Auto-recover if services crash (every 5 min)
echo.
powershell.exe -ExecutionPolicy Bypass -File "%~dp0INSTALL_SERVICE.ps1"
pause
