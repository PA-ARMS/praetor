@echo off
echo ============================================================
echo REBUILD CHROMADB SEARCH INDEX
echo ============================================================
echo.
echo This will fix the corrupted HNSW index that is causing
echo vector search to hang.
echo.
echo WARNING: This may take 5-30 minutes!
echo.
pause

cd /d C:\LAWFIRMAI

echo.
echo Activating Python environment...
call venv\Scripts\activate.bat

echo.
echo Running index rebuild...
python scripts\rebuild_hnsw_index.py

echo.
echo ============================================================
pause

