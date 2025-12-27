@echo off
echo Starting Virginia Legal AI Server...
cd /d %~dp0..
set SCENARIO_DB_ENABLED=True
python server/main.py
pause

