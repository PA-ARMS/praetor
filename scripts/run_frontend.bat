@echo off
REM Run frontend from client folder using this script's location
cd /d "%~dp0..\client"

echo Frontend starting from: %CD%
echo.

call npm run dev

if errorlevel 1 (
    echo.
    echo Frontend exited with an error. See above.
)
pause
