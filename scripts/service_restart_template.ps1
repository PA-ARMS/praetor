# AK Legal Vault - Restart Script
$ErrorActionPreference = 'SilentlyContinue'
$AppPath = 'APPPATH'
$LogPath = 'LOGPATH'
$StartupScriptPath = 'STARTUPSCRIPTPATH'
$KillPortScript = 'APPPATH\scripts\kill_port.ps1'

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $LogPath 'service.log') -Value "[$timestamp] $Message"
}

Write-Log "Restart initiated - stopping existing processes..."

# Kill by port (most reliable) then by process
if (Test-Path $KillPortScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $KillPortScript -Port 5001
    Write-Log "Port 5001 freed"
}
Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

$procs = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*server.main*' }
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Log "Stopped backend (PID: $($_.ProcessId))" }

$nodeProcs = Get-CimInstance Win32_Process -Filter "name='node.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*vite*' -or $_.CommandLine -like '*npm*' }
$nodeProcs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Log "Stopped frontend (PID: $($_.ProcessId))" }

Start-Sleep -Seconds 5
Write-Log "Starting services..."
& $StartupScriptPath
Write-Log "Restart complete"
