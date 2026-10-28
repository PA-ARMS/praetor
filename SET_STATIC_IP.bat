@echo off
REM Set static IP so PC keeps same address on local network
REM Must run as Administrator
echo.
echo Setting static IP for Virginia Legal AI server...
echo (Uses current IP - run once to lock it in)
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\set_static_ip.ps1" %*
pause
