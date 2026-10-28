#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Stops processes listening on dev ports using taskkill (works for Session 0 / SYSTEM tasks).

.DESCRIPTION
    When the backend is started via INSTALL_SERVICE.ps1 (scheduled task as SYSTEM), it runs in
    Session 0. A normal user cannot Stop-Process that PID; Administrator can taskkill /F it.

    Optional: temporarily stop the health monitor task so it does not respawn the backend
    before you finish testing. Re-enable the task afterward, or run INSTALL_SERVICE.ps1 again.

.PARAMETER Port
    Ports to clear (default: 5001 backend, 3000 frontend, 3001 vite alt).

.PARAMETER PauseMonitorTask
    If true, stops AKLegalVault_Monitor scheduled task (if present) to prevent auto-restart.
#>
param(
    [int[]]$Port = @(5001, 3000, 3001),
    [switch]$PauseMonitorTask
)

$ErrorActionPreference = 'SilentlyContinue'

if ($PauseMonitorTask) {
    # Disable (not just Stop) so the task does not run again in a few minutes and respawn servers.
    $names = @('AKLegalVault_Monitor')
    foreach ($name in $names) {
        $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($t) {
            Write-Host "Disabling scheduled task: $name (auto-recovery paused)"
            Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            Disable-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        } else {
            Write-Host "Task not found: $name (skip — install via INSTALL_SERVICE.ps1 if you use auto-monitor)"
        }
    }
    Write-Host ""
    Write-Host "Re-enable later: run RESUME_VAULT_MONITOR_ADMIN.bat as Administrator."
    Write-Host ""
}

foreach ($p in $Port) {
    $pids = [System.Collections.Generic.HashSet[int]]::new()
    try {
        Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop | ForEach-Object {
            [void]$pids.Add($_.OwningProcess)
        }
    } catch {
        $out = & cmd.exe /c "netstat -ano 2>nul" | ForEach-Object { $_ }
        foreach ($l in $out) {
            if ($l -match ":$p\s+.*LISTENING\s+(\d+)\s*$") {
                [void]$pids.Add([int]$Matches[1])
            }
        }
    }
    foreach ($procId in $pids) {
        if ($procId -le 0) { continue }
        Write-Host "taskkill /F /PID $procId (port $p)"
        $null = & cmd.exe /c "taskkill /F /PID $procId 2>&1"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "taskkill failed for PID $procId (exit $LASTEXITCODE)"
        }
    }
}

Write-Host "Done. Ports cleared (if PIDs existed)."
