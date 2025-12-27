@echo off
echo ============================================================
echo SCOTUS OPINION DATABASE BUILDER
echo ============================================================
echo.
echo This will fetch and ingest all SCOTUS opinions.
echo.
pause

python scripts\fetch_scotus_opinions.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Fetching failed!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Now ingesting opinions into RAG system...
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
pause






