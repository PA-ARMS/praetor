@echo off
REM Run test suite
echo ========================================
echo   Running Test Suite
echo ========================================
echo.

REM Check if pytest is installed
python -c "import pytest" 2>nul
if %errorLevel% neq 0 (
    echo ERROR: pytest is not installed
    echo Install with: pip install pytest
    pause
    exit /b 1
)

REM Run tests
echo Running API tests...
python -m pytest tests/test_api.py -v

echo.
echo Running authentication tests...
python -m pytest tests/test_auth.py -v

echo.
echo ========================================
echo   Test Suite Complete
echo ========================================
pause

