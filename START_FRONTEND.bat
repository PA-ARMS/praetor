@echo off
title Virginia Legal AI - Frontend Server
color 0A

cd /d "%~dp0\client"

echo ========================================
echo   Virginia Legal AI - Frontend Server
echo   Port 3000
echo ========================================
echo.
echo Starting frontend...
echo.
npm run dev

if errorlevel 1 (
    echo.
    echo Frontend exited with an error. Run: npm install
)
pause
