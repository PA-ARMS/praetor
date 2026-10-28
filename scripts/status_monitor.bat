@echo off
title Virginia Legal AI - Status Monitor
color 0A
mode con: cols=80 lines=25

echo ========================================
echo   Virginia Legal AI - Status Monitor
echo ========================================
echo.
echo System Status:
echo.
echo Backend:  http://localhost:5001
echo Frontend: http://localhost:3000 ^(or 3001 if 3000 is busy^)
echo.
echo Checking services every 5 seconds...
echo Press Ctrl+C to close this window
echo.
echo ========================================
echo.

:loop
timeout /t 5 /nobreak >nul
cls
echo ========================================
echo   Virginia Legal AI - Status Monitor
echo ========================================
echo.
echo Backend:  http://localhost:5001
echo Frontend: http://localhost:3000 ^(or 3001 if 3000 is busy^)
echo.
echo Last Check: %date% %time%
echo.

REM Check backend
powershell -NoProfile -Command "$time = Get-Date -Format 'HH:mm:ss'; try { $null = Invoke-WebRequest -Uri 'http://localhost:5001/health' -TimeoutSec 3 -UseBasicParsing; Write-Host \"[$time] Backend:  RUNNING\" -ForegroundColor Green } catch { Write-Host \"[$time] Backend:  NOT RUNNING\" -ForegroundColor Red }"

REM Check frontend
powershell -NoProfile -Command "$time = Get-Date -Format 'HH:mm:ss'; $frontendPort = 3000; try { $null = Invoke-WebRequest -Uri \"http://localhost:3000\" -TimeoutSec 3 -UseBasicParsing; Write-Host \"[$time] Frontend: RUNNING (http://localhost:3000)\" -ForegroundColor Green } catch { try { $null = Invoke-WebRequest -Uri \"http://localhost:3001\" -TimeoutSec 3 -UseBasicParsing; Write-Host \"[$time] Frontend: RUNNING (http://localhost:3001)\" -ForegroundColor Green } catch { Write-Host \"[$time] Frontend: NOT RUNNING\" -ForegroundColor Red } }"

echo.
echo Checking again in 5 seconds...
echo Press Ctrl+C to close this window
echo.
goto loop

