# Alternative method to get Tesseract installer
# This uses GitHub API to find the latest release

Write-Host "Finding latest Tesseract OCR release..." -ForegroundColor Cyan

try {
    # Get latest release info from GitHub
    $releaseUrl = "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest"
    $releaseInfo = Invoke-RestMethod -Uri $releaseUrl -UseBasicParsing
    
    Write-Host "Latest release: $($releaseInfo.tag_name)" -ForegroundColor Green
    
    # Find Windows installer asset
    $installerAsset = $releaseInfo.assets | Where-Object { $_.name -like "*w64-setup*.exe" } | Select-Object -First 1
    
    if ($installerAsset) {
        Write-Host "Found installer: $($installerAsset.name)" -ForegroundColor Green
        Write-Host "Download URL: $($installerAsset.browser_download_url)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Opening download page..." -ForegroundColor Cyan
        Start-Process $installerAsset.browser_download_url
        Write-Host ""
        Write-Host "The installer should start downloading in your browser." -ForegroundColor Yellow
        Write-Host "After download:" -ForegroundColor Yellow
        Write-Host "  1. Run the installer" -ForegroundColor Yellow
        Write-Host "  2. Check 'Add to PATH' during installation" -ForegroundColor Yellow
        Write-Host "  3. Complete the installation" -ForegroundColor Yellow
    } else {
        Write-Host "Could not find Windows installer in release assets." -ForegroundColor Yellow
        Write-Host "Please visit: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
        Start-Process "https://github.com/UB-Mannheim/tesseract/wiki"
    }
} catch {
    Write-Host "Could not fetch release info automatically." -ForegroundColor Yellow
    Write-Host "Opening download page manually..." -ForegroundColor Cyan
    Start-Process "https://github.com/UB-Mannheim/tesseract/wiki"
    Write-Host ""
    Write-Host "Please download the latest Windows installer from the page." -ForegroundColor Yellow
}




