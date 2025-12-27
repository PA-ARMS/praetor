@echo off
title Virginia Legal AI - System Shutdown
color 0C

echo ========================================
echo   Virginia Legal AI System Shutdown
echo ========================================
echo.

echo Stopping services...

REM Kill Python processes running uvicorn
taskkill /FI "WINDOWTITLE eq Virginia Legal AI - Backend Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Virginia Legal AI - Frontend Server*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Virginia Legal AI - Status Monitor*" /T /F >nul 2>&1

REM Also kill by process name (backup method)
for /f "tokens=2" %%a in ('tasklist ^| findstr /i "node.exe python.exe"') do (
    taskkill /PID %%a /F >nul 2>&1
)

timeout /t 2 /nobreak >nul

echo.
echo Services stopped.
echo.
pause

