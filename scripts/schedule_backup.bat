@echo off
REM Schedule daily database backups using Windows Task Scheduler
REM Run this script as Administrator to set up automatic backups

echo ========================================
echo   Database Backup Scheduler Setup
echo ========================================
echo.

REM Get script directory
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script must be run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Setting up daily backup task...
echo.

REM Create task to run backup daily at 2 AM
schtasks /Create /TN "LegalAI_DailyBackup" ^
    /TR "python \"%PROJECT_DIR%\scripts\backup_database.py\"" ^
    /SC DAILY /ST 02:00 ^
    /RU SYSTEM ^
    /F

if %errorLevel% equ 0 (
    echo.
    echo ✓ Daily backup task created successfully!
    echo   Task will run daily at 2:00 AM
    echo.
    echo To view the task:
    echo   schtasks /Query /TN "LegalAI_DailyBackup"
    echo.
    echo To delete the task:
    echo   schtasks /Delete /TN "LegalAI_DailyBackup" /F
) else (
    echo.
    echo ✗ Failed to create backup task
    echo   Error code: %errorLevel%
)

pause

