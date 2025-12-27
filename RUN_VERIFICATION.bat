@echo off
echo ============================================================
echo LEGAL AI SYSTEM - PRODUCTION VERIFICATION
echo ============================================================
echo.

cd /d C:\LAWFIRMAI

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo Running verification suite...
echo.

python scripts\production_verification_suite.py

echo.
echo ============================================================
echo Verification complete!
echo.
echo Check these files for results:
echo   - data\PRODUCTION_VERIFICATION_REPORT.txt
echo   - data\production_verification.json
echo ============================================================
echo.
pause


















