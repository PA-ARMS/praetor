# PowerShell script to download and install Tesseract OCR on Windows
# This script attempts to download and install Tesseract automatically

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Tesseract OCR Auto-Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if already installed
$tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $tesseractPath) {
    Write-Host "[OK] Tesseract is already installed at: $tesseractPath" -ForegroundColor Green
    & $tesseractPath --version
    exit 0
}

Write-Host "[INFO] Tesseract OCR not found. Starting installation..." -ForegroundColor Yellow
Write-Host ""

# Latest stable version URL (as of 2024)
# You may need to update this URL to the latest release
$installerUrl = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240619.exe"
$installerPath = "$env:TEMP\tesseract-installer.exe"

Write-Host "Step 1: Downloading Tesseract OCR installer..." -ForegroundColor Cyan
Write-Host "URL: $installerUrl" -ForegroundColor Gray
Write-Host ""

try {
    # Download the installer
    Write-Host "Downloading (this may take a few minutes)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "[OK] Download complete!" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Step 2: Installing Tesseract OCR..." -ForegroundColor Cyan
    Write-Host "The installer will open. Please:" -ForegroundColor Yellow
    Write-Host "  1. Click 'Next' through the installation wizard" -ForegroundColor Yellow
    Write-Host "  2. IMPORTANT: Check 'Add to PATH' when prompted" -ForegroundColor Yellow
    Write-Host "  3. Complete the installation" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Starting installer..." -ForegroundColor Cyan
    
    # Run the installer
    Start-Process -FilePath $installerPath -Wait
    
    Write-Host ""
    Write-Host "Step 3: Verifying installation..." -ForegroundColor Cyan
    
    # Refresh PATH environment variable
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    # Check if installation was successful
    Start-Sleep -Seconds 2
    
    if (Test-Path $tesseractPath) {
        Write-Host "[SUCCESS] Tesseract OCR installed successfully!" -ForegroundColor Green
        & $tesseractPath --version
        Write-Host ""
        Write-Host "You may need to restart your terminal/server for PATH changes to take effect." -ForegroundColor Yellow
    } else {
        Write-Host "[WARNING] Installation completed but Tesseract not found in expected location." -ForegroundColor Yellow
        Write-Host "You may need to:" -ForegroundColor Yellow
        Write-Host "  1. Restart your computer" -ForegroundColor Yellow
        Write-Host "  2. Or manually add Tesseract to PATH" -ForegroundColor Yellow
        Write-Host "  3. Or specify the path in the OCR service configuration" -ForegroundColor Yellow
    }
    
    # Clean up installer
    if (Test-Path $installerPath) {
        Remove-Item $installerPath -Force
    }
    
} catch {
    Write-Host "[ERROR] Failed to download/install Tesseract: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual installation:" -ForegroundColor Yellow
    Write-Host "  1. Visit: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "  2. Download the latest installer" -ForegroundColor Yellow
    Write-Host "  3. Run it and check 'Add to PATH'" -ForegroundColor Yellow
    exit 1
}




