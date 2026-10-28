#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Schedule annual Virginia Code corpus refresh for AK Legal Vault.

.DESCRIPTION
    Creates a Windows scheduled task that runs scripts/update_va_legal_corpus.py
    every July 15 at 2:00 AM (after the General Assembly session and typical
    effective dates). Also supports -RunNow and -Uninstall.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup_va_law_update_task.ps1
    powershell -ExecutionPolicy Bypass -File scripts\setup_va_law_update_task.ps1 -RunNow
#>
param(
    [switch]$Uninstall,
    [switch]$RunNow,
    [string]$ScheduleMonth = "7",
    [string]$ScheduleDay = "15",
    [string]$ScheduleTime = "02:00"
)

$ErrorActionPreference = "Stop"

$AppPath = Split-Path -Parent $PSScriptRoot
$TaskName = "AKLegalVault_VA_LawUpdate"
$LogPath = Join-Path $AppPath "logs"
$UpdateScript = Join-Path $AppPath "scripts\update_va_legal_corpus.py"
$WrapperBat = Join-Path $AppPath "RUN_VA_LAW_UPDATE_SCHEDULED.bat"

if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

# Resolve Python
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command py -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and retry."
}

$PythonExeEscaped = $PythonExe -replace "'", "''"

# Hidden scheduled runner (logs to logs/va_law_update.log)
$batContent = @"
@echo off
cd /d "$AppPath"
set PYTHONIOENCODING=utf-8
echo [%date% %time%] VA law corpus update started >> logs\va_law_update.log
"$PythonExe" scripts\update_va_legal_corpus.py --force >> logs\va_law_update.log 2>&1
echo [%date% %time%] Exit code %ERRORLEVEL% >> logs\va_law_update.log
exit /b %ERRORLEVEL%
"@
Set-Content -Path $WrapperBat -Value $batContent -Encoding ASCII

function Uninstall-Task {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed scheduled task: $TaskName" -ForegroundColor Green
}

function Install-Task {
    Uninstall-Task

    $monthNames = @(
        "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
        "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
    )
    $mo = $monthNames[[int]$ScheduleMonth]
    if (-not $mo) {
        Write-Error "Invalid ScheduleMonth: $ScheduleMonth (use 1-12)"
    }

    $st = $ScheduleTime
    if ($st -match "^\d{1,2}:\d{2}$") {
        $parts = $st.Split(":")
        $st = "{0:D2}:{1}" -f [int]$parts[0], $parts[1]
    }

    $createArgs = @(
        "/Create", "/TN", $TaskName,
        "/TR", "cmd.exe /c `"$WrapperBat`"",
        "/SC", "YEARLY", "/MO", $mo, "/D", $ScheduleDay,
        "/ST", $st,
        "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"
    )
    & schtasks.exe @createArgs | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks failed with exit code $LASTEXITCODE"
    }

    Write-Host "[OK] Scheduled task created: $TaskName" -ForegroundColor Green
    Write-Host "     Runs yearly every $mo $ScheduleDay at $st" -ForegroundColor Cyan
    Write-Host "     Log: $LogPath\va_law_update.log" -ForegroundColor Cyan
}

if ($Uninstall) {
    Uninstall-Task
    exit 0
}

Write-Host ""
Write-Host "  Virginia Law Annual Update - Task Setup" -ForegroundColor Yellow
Write-Host "  =======================================" -ForegroundColor Yellow
Write-Host ""

Install-Task

if ($RunNow) {
    Write-Host "Starting update now (background)..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Task started. Monitor: logs\va_law_update.log" -ForegroundColor Green
}

Write-Host ""
Write-Host "Manual run anytime:" -ForegroundColor White
Write-Host "  UPDATE_VA_LAWS.bat" -ForegroundColor Gray
Write-Host "  python scripts\update_va_legal_corpus.py --force" -ForegroundColor Gray
Write-Host ""
