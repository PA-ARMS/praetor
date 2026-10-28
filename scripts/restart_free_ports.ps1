# Free dev ports before (re)starting backend/frontend.
# 1) Tries scripts/kill_port.ps1 (user session).
# 2) If anything still LISTENING (e.g. SYSTEM / Session 0 from scheduled task), launches
#    stop_backend_elevated.ps1 with UAC so taskkill runs as Administrator.
param(
    [int[]]$Ports = @(5001, 3000, 3001)
)

$ErrorActionPreference = 'Continue'
$kill = Join-Path $PSScriptRoot 'kill_port.ps1'
$elev = Join-Path $PSScriptRoot 'stop_backend_elevated.ps1'

foreach ($p in $Ports) {
    if (Test-Path $kill) {
        & $kill -Port $p
    }
}

function Test-AnyPortListen {
    param([int[]]$PortList)
    foreach ($p in $PortList) {
        try {
            if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) {
                return $true
            }
        } catch {}
        $lines = & cmd.exe /c "netstat -ano 2>nul" | ForEach-Object { $_ }
        foreach ($l in $lines) {
            if ($l -match "LISTENING" -and $l -match ":$p\s") {
                return $true
            }
        }
    }
    return $false
}

if (-not (Test-AnyPortListen -PortList $Ports)) {
    Write-Host "Ports cleared ($($Ports -join ', ')). No Administrator prompt needed." -ForegroundColor Green
    exit 0
}

Write-Host "Port(s) $($Ports -join ', ') still in use (common: Python/Node started as SYSTEM from a scheduled task)." -ForegroundColor Yellow
Write-Host "Requesting elevated cleanup (UAC prompt)..." -ForegroundColor Yellow

if (-not (Test-Path $elev)) {
    Write-Host "Missing: $elev" -ForegroundColor Red
    exit 1
}

try {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File',
        $elev
    )
} catch {
    Write-Host "Elevated cleanup declined or failed: $_" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

if (Test-AnyPortListen -PortList $Ports) {
    Write-Host "Still listening. Run: STOP_BACKEND_ADMIN.bat (accept UAC), or STOP_BACKEND_PAUSE_MONITOR_ADMIN.bat if the monitor respawns servers." -ForegroundColor Yellow
    exit 2
}

Write-Host "Ports cleared after elevated cleanup." -ForegroundColor Green
exit 0
