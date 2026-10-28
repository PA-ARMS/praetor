@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo.
echo  Virginia Legal AI - Update Virginia Law Corpus
echo  ================================================
echo.
echo  Downloads current Code of Virginia from law.lis.virginia.gov
echo  and re-indexes statutes into the RAG database.
echo.
echo  This may take 30-90 minutes depending on hardware.
echo.

python scripts\update_va_legal_corpus.py --force
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% equ 0 (
    echo  Update completed successfully.
) else (
    echo  Update finished with errors. See data\va_law_update_status.json
)
echo.

pause
exit /b %EXITCODE%
