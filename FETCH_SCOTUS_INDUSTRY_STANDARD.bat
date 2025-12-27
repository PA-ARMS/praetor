@echo off
echo ============================================================
echo SCOTUS OPINION DATABASE BUILDER (INDUSTRY STANDARD)
echo ============================================================
echo.
echo This uses CAP (Caselaw Access Project) - Harvard Law School
echo Industry-standard source for historical SCOTUS opinions
echo.
echo NOTE: You need a FREE CAP API key:
echo   1. Visit: https://case.law/user/register/
echo   2. Register for free account
echo   3. Get API key from: https://case.law/user/profile/
echo   4. Set: set CAP_API_KEY=your_key_here
echo.
pause

if "%CAP_API_KEY%"=="" (
    echo.
    echo WARNING: CAP_API_KEY not set!
    echo The script will continue but with limited access.
    echo.
    pause
)

echo.
echo ============================================================
echo STEP 1: Fetching Recent Opinions (SCOTUS.gov)
echo ============================================================
echo.

python scripts\fetch_scotus_opinions.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Recent opinions fetch had issues, but continuing...
)

echo.
echo ============================================================
echo STEP 2: Fetching Historical Opinions (CAP API)
echo ============================================================
echo.

python scripts\fetch_scotus_industry_standard.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Historical opinions fetch failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo STEP 3: Ingesting All SCOTUS Opinions
echo ============================================================
echo.

python scripts\ingest_scotus_opinions.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Ingestion failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SCOTUS DATABASE BUILD COMPLETE!
echo ============================================================
echo.
echo Your system now has a comprehensive SCOTUS opinion database
echo using industry-standard sources and practices!
echo.
pause






