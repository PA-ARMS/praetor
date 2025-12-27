@echo off
title AK Legal Vault - Service Setup
color 0E

echo.
echo  ╔═══════════════════════════════════════════════════════════╗
echo  ║                                                           ║
echo  ║              AK LEGAL VAULT                               ║
echo  ║              Service Setup Wizard                         ║
echo  ║                                                           ║
echo  ╚═══════════════════════════════════════════════════════════╝
echo.

REM Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  This setup requires Administrator privileges.
    echo.
    echo  Right-click and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo  Launching service installer...
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0INSTALL_SERVICE.ps1"

pause

