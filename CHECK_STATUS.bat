@echo off
echo Checking background job status...
tasklist /FI "IMAGENAME eq python.exe"
echo.
echo Checking VA_COURTS_SELFHELP file count...
dir "data\sources\VA_COURTS_SELFHELP" | find /c /v ""
echo.
echo Checking latest files...
dir /O-D "data\sources\VA_COURTS_SELFHELP" | findstr /n . | findstr "^[1-5]:"
pause
