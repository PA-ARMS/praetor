@echo off
echo ========================================
echo   Batch Files Cleanup
echo ========================================
echo.
echo This will remove unnecessary batch files.
echo.
pause

REM Remove old/duplicate startup files
if exist "START_SYSTEM_WORKING.bat" (
    echo Removing START_SYSTEM_WORKING.bat...
    del "START_SYSTEM_WORKING.bat"
)

if exist "START_SYSTEM_FIXED.bat" (
    echo Removing START_SYSTEM_FIXED.bat...
    del "START_SYSTEM_FIXED.bat"
)

if exist "START_FRONTEND_DEBUG.bat" (
    echo Removing START_FRONTEND_DEBUG.bat...
    del "START_FRONTEND_DEBUG.bat"
)

REM Remove one-time setup files (already done)
if exist "INSTALL_TTS.bat" (
    echo Removing INSTALL_TTS.bat...
    del "INSTALL_TTS.bat"
)

if exist "INSTALL_TTS_DEPS.bat" (
    echo Removing INSTALL_TTS_DEPS.bat...
    del "INSTALL_TTS_DEPS.bat"
)

if exist "SETUP_THEFIRM.bat" (
    echo Removing SETUP_THEFIRM.bat...
    del "SETUP_THEFIRM.bat"
)

if exist "OPEN_FIREWALL_PORTS.bat" (
    echo Removing OPEN_FIREWALL_PORTS.bat...
    del "OPEN_FIREWALL_PORTS.bat"
)

REM Remove specific use case files (can be recreated if needed)
if exist "START_BULK_DOWNLOAD.bat" (
    echo Removing START_BULK_DOWNLOAD.bat...
    del "START_BULK_DOWNLOAD.bat"
)

if exist "DOWNLOAD_10K_CASES.bat" (
    echo Removing DOWNLOAD_10K_CASES.bat...
    del "DOWNLOAD_10K_CASES.bat"
)

if exist "LEARN_AND_TRAIN_MONITOR.bat" (
    echo Removing LEARN_AND_TRAIN_MONITOR.bat...
    del "LEARN_AND_TRAIN_MONITOR.bat"
)

if exist "START_CONTROL_PANEL.bat" (
    echo Removing START_CONTROL_PANEL.bat...
    del "START_CONTROL_PANEL.bat"
)

REM Remove scripts directory one-time files
if exist "scripts\auto_process.bat" (
    echo Removing scripts\auto_process.bat...
    del "scripts\auto_process.bat"
)

if exist "scripts\open_firewall_rules.bat" (
    echo Removing scripts\open_firewall_rules.bat...
    del "scripts\open_firewall_rules.bat"
)

if exist "scripts\setup_hosts_file.bat" (
    echo Removing scripts\setup_hosts_file.bat...
    del "scripts\setup_hosts_file.bat"
)

echo.
echo ========================================
echo   Cleanup Complete
echo ========================================
echo.
echo Kept essential files:
echo   - START_SYSTEM.bat (main startup)
echo   - START_SYSTEM_SINGLE_WINDOW.bat (alternative startup)
echo   - STOP_SYSTEM.bat (shutdown)
echo   - CHECK_PROGRESS.bat (check learning progress)
echo   - LEARN_AND_TRAIN.bat (learning system)
echo   - QUICK_LEARN.bat (quick learning)
echo   - scripts\start_server.bat (server startup)
echo   - scripts\start_client.bat (client startup)
echo.
pause

