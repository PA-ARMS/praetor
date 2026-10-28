#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Re-enables AKLegalVault_Monitor after STOP_BACKEND_PAUSE_MONITOR_ADMIN.bat disabled it.
#>
$ErrorActionPreference = 'Continue'

$names = @('AKLegalVault_Monitor')
foreach ($name in $names) {
    $t = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $t) {
        Write-Warning "Task not found: $name — run INSTALL_SERVICE.ps1 to create it."
        continue
    }
    try {
        Enable-ScheduledTask -TaskName $name
        Write-Host "Enabled: $name"
    } catch {
        Write-Warning "Could not enable ${name}: $_"
    }
}

Write-Host "Done. Health monitor will run on its next schedule (within a few minutes if configured)."
