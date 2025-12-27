# Restart Backend Server Script
# Kills existing backend process and starts a new one

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Restarting Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the project root directory
$projectRoot = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
Set-Location $projectRoot

# Set Python path
$env:PYTHONPATH = $projectRoot

# Ensure eSpeak NG is on PATH for Coqui TTS phonemizer
$espeakPaths = @(
    "C:\Program Files\eSpeak NG",
    "C:\Program Files (x86)\eSpeak NG"
)
foreach ($p in $espeakPaths) {
    if (Test-Path $p) {
        if (-not ($env:PATH -split ";" | ForEach-Object { $_.Trim() } | Where-Object { $_ -eq $p })) {
            $env:PATH = "$env:PATH;$p"
        }
    }
}

# Find and kill existing backend processes
Write-Host "Stopping existing backend processes..." -ForegroundColor Yellow

# Find processes using port 5000
$processes = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($processes) {
    foreach ($procId in $processes) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -eq "python") {
                Write-Host "  Killing Python process (PID: $procId)..." -ForegroundColor Gray
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # Process may have already terminated
        }
    }
    Start-Sleep -Seconds 2
}

# Wait a moment for port to be released
Write-Host "  Waiting for port 5000 to be released..." -ForegroundColor Gray
Start-Sleep -Seconds 2

# Start backend server
Write-Host ""
Write-Host "Starting backend server..." -ForegroundColor Green
Write-Host "  Command: python -m uvicorn server.main:app --host 0.0.0.0 --port 5000" -ForegroundColor Gray
Write-Host ""
Write-Host "Backend server starting in new window..." -ForegroundColor Yellow
Write-Host ""

# Start in new window
Start-Process cmd -ArgumentList "/k", "cd /d `"$projectRoot`" && set PYTHONPATH=$projectRoot && python -m uvicorn server.main:app --host 0.0.0.0 --port 5000"

# Wait a moment
Start-Sleep -Seconds 3

# Check if server started
Write-Host "Checking server status..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  Backend server is running!" -ForegroundColor Green
    Write-Host "  Health check: http://localhost:5000/health" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "  Backend may still be starting..." -ForegroundColor Yellow
    Write-Host "  Check the backend window for status." -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Backend restart complete!" -ForegroundColor Green
Write-Host ""
