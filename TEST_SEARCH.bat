@echo off
echo ======================================================================
echo SEARCH FUNCTIONALITY TEST
echo This may take 1-2 minutes for the first query
echo (Loading 54,000+ legal documents into memory)
echo ======================================================================
echo.

cd /d C:\LAWFIRMAI
python scripts/test_chroma_timeout.py

echo.
echo ======================================================================
echo Test complete!
echo ======================================================================
pause


















