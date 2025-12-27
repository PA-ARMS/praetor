@echo off
REM Script to help install Tesseract OCR on Windows
echo ========================================
echo Tesseract OCR Installation Helper
echo ========================================
echo.
echo This script will help you install Tesseract OCR for Windows.
echo.
echo STEP 1: Download Tesseract OCR
echo.
echo Please visit: https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo Download the latest installer (e.g., tesseract-ocr-w64-setup-5.x.x.exe)
echo.
pause
echo.
echo STEP 2: Run the installer
echo.
echo When installing:
echo   - Check "Add to PATH" during installation
echo   - OR note the installation directory (usually C:\Program Files\Tesseract-OCR)
echo.
pause
echo.
echo STEP 3: Verify installation
echo.
echo Testing Tesseract installation...
tesseract --version
if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS! Tesseract OCR is installed and working.
    echo.
    echo You can now use OCR features in AKLAWMS.
) else (
    echo.
    echo Tesseract not found in PATH.
    echo.
    echo If you installed Tesseract but it's not found:
    echo   1. Add Tesseract to your system PATH
    echo   2. OR restart your computer
    echo   3. OR manually set the path in the code
    echo.
    echo Default installation path: C:\Program Files\Tesseract-OCR
    echo.
)
echo.
pause

