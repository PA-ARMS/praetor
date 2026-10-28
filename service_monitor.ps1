# AK Legal Vault - Health Monitor (runs every 5 min via scheduled task)
# Automatically restarts whatever is down - backend only, frontend only, or both
$ErrorActionPreference = 'SilentlyContinue'
$AppPath = 'C:\LAWFIRMAI'
$LogPath = 'C:\LAWFIRMAI\logs'
$StartupScriptPath = 'C:\LAWFIRMAI\service_startup.ps1'
$KillPortScript = 'C:\LAWFIRMAI\scripts\kill_port.ps1'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $LogPath 'monitor.log') -Value "[$timestamp] $Message"
}

$backendRunning = $false
try {
    $response = Invoke-RestMethod -Uri 'http://localhost:5001/health' -TimeoutSec 8
    if ($response.status -eq 'healthy') { $backendRunning = $true }
} catch { }

$frontendRunning = $false
try {
    $response = Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 8 -UseBasicParsing
    if ($response.StatusCode -eq 200) { $frontendRunning = $true }
} catch { }

if ($backendRunning -and $frontendRunning) { exit 0 }

Write-Log "Service down - Backend: $backendRunning, Frontend: $frontendRunning"

# Full restart is most reliable (handles port conflicts, zombie processes)
Write-Log "Initiating automatic recovery (full restart)..."
& 'C:\LAWFIRMAI\service_restart.ps1'

