# AK Legal Vault - Health Monitor
$ErrorActionPreference = 'SilentlyContinue'
$AppPath = 'APPPATH'
$LogPath = 'LOGPATH'
$RestartScriptPath = 'RESTARTSCRIPTPATH'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $LogPath 'monitor.log') -Value "[$timestamp] $Message"
}

$backendRunning = $false
try {
    $response = Invoke-RestMethod -Uri 'http://localhost:5001/health' -TimeoutSec 10
    if ($response.status -eq 'healthy') { $backendRunning = $true }
} catch { }

$frontendRunning = $false
try {
    $response = Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 10 -UseBasicParsing
    if ($response.StatusCode -eq 200) { $frontendRunning = $true }
} catch { }

if (-not $backendRunning -or -not $frontendRunning) {
    Write-Log "Service down detected - Backend: $backendRunning, Frontend: $frontendRunning"
    Write-Log "Initiating automatic recovery..."
    & $RestartScriptPath
}
