# AK Legal Vault - Startup Script
$ErrorActionPreference = 'SilentlyContinue'
$AppPath = 'APPPATH'
$LogPath = 'LOGPATH'
$PythonExe = 'PYTHONEXE'
$NpmCmd = 'NPMCMD'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $LogPath 'service.log') -Value "[$timestamp] $Message"
}

if (-not (Test-Path $LogPath)) { New-Item -ItemType Directory -Path $LogPath -Force | Out-Null }

Write-Log "Starting AK Legal Vault..."
Start-Sleep -Seconds STARTUPDELAY
Set-Location $AppPath
$env:PYTHONPATH = $AppPath
$env:SCENARIO_DB_ENABLED = 'True'

# Stop any process using our port (prevents "port already in use" errors)
$backendPort = 5001
Write-Log "Releasing port $backendPort..."
$portProcs = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $portProcs) {
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Log "Stopped process on port $backendPort (PID: $procId)"
    } catch {
        $null = & cmd.exe /c "taskkill /F /PID $procId" 2>&1
        if ($LASTEXITCODE -eq 0) { Write-Log "Stopped via taskkill (PID: $procId)" }
        else { Write-Log "Could not stop PID $procId (need Admin if SYSTEM/Session 0): $_" }
    }
}
$pythonProcs = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*server.main*' }
$pythonProcs | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Write-Log "Stopped backend (PID: $($_.ProcessId))" } catch {} }
Start-Sleep -Seconds 4

Write-Log "Starting backend server..."
$backendOk = $false
foreach ($attempt in 1..2) {
    try {
        $health = Invoke-RestMethod -Uri 'http://localhost:5001/health' -TimeoutSec 3 -ErrorAction Stop
        if ($health.status -eq 'healthy') { Write-Log "Backend already running"; $backendOk = $true; break }
    } catch { }
    if ($attempt -gt 1) {
        Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
            $oid = $_.OwningProcess
            try { Stop-Process -Id $oid -Force -ErrorAction Stop } catch { $null = & cmd.exe /c "taskkill /F /PID $oid" 2>&1 }
        }
        Start-Sleep -Seconds 4
    }
    $backendLog = Join-Path $LogPath 'backend.log'
    $backendErr = Join-Path $LogPath 'backend_error.log'
    $backendProc = Start-Process -FilePath $PythonExe -ArgumentList '-m','uvicorn','server.main:app','--host','0.0.0.0','--port','5001','--timeout-keep-alive','600' -WorkingDirectory $AppPath -RedirectStandardOutput $backendLog -RedirectStandardError $backendErr -PassThru
    Write-Log "Backend start attempt $attempt (PID: $($backendProc.Id))"
    Start-Sleep -Seconds 12
    try {
        $h = Invoke-RestMethod -Uri 'http://localhost:5001/health' -TimeoutSec 5 -ErrorAction Stop
        if ($h.status -eq 'healthy') { $backendOk = $true; break }
    } catch { }
}
if (-not $backendOk) { Write-Log "WARNING: Backend may not have started" }
Start-Sleep -Seconds 3

Write-Log "Starting frontend server..."
# Use npm.cmd (not .ps1) - Start-Process with .ps1 opens in Notepad instead of executing
$npmCmd = $NpmCmd -replace '\.ps1$', '.cmd'
if (-not (Test-Path $npmCmd)) { $npmCmd = $NpmCmd }
Start-Process -FilePath $npmCmd -ArgumentList 'run', 'dev' -WindowStyle Hidden -WorkingDirectory (Join-Path $AppPath 'client')
Write-Log "Services started successfully"
