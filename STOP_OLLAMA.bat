@echo off
title Stop Ollama
echo Stopping Ollama...
taskkill /F /IM ollama.exe 2>nul
if errorlevel 1 (echo Ollama was not running.) else (echo Ollama stopped.)
timeout /t 2 /nobreak >nul
echo.
echo To uninstall: Win + I -^> Apps -^> find Ollama -^> Uninstall
echo To reinstall: https://ollama.com/download
echo.
pause
