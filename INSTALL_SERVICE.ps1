#Requires -RunAsAdministrator
<#
.SYNOPSIS
    AK Legal Vault - Windows Service Installer
    
.DESCRIPTION
    This script sets up:
    1. Auto-start on Windows boot (runs before user login)
    2. Automatic midnight restart for optimal performance
    3. System monitoring and auto-recovery
    
.NOTES
    Author: LexTech Systems
    Version: 1.0.0
    Requires: Administrator privileges
#>

param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$AtLogon
)

$ErrorActionPreference = "Stop"

# Configuration
$AppName = "AKLegalVault"
$AppDisplayName = "AK Legal Vault"
$AppPath = $PSScriptRoot
$LogPath = Join-Path $AppPath "logs"
$StartupDelay = 5  # Seconds to wait before starting (was 30 for boot; reduced for faster manual start)

# Colors for console output
function Write-Success { Write-Host $args[0] -ForegroundColor Green }
function Write-Info { Write-Host $args[0] -ForegroundColor Cyan }
function Write-Warning { Write-Host $args[0] -ForegroundColor Yellow }
function Write-Error { Write-Host $args[0] -ForegroundColor Red }

# Header
Clear-Host
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor DarkYellow
Write-Host "  |                                                           |" -ForegroundColor DarkYellow
Write-Host "  |           " -NoNewline -ForegroundColor DarkYellow
Write-Host "AK LEGAL VAULT" -NoNewline -ForegroundColor Yellow
Write-Host "                              |" -ForegroundColor DarkYellow
Write-Host "  |           " -NoNewline -ForegroundColor DarkYellow
Write-Host "Service Management System" -NoNewline -ForegroundColor White
Write-Host "                    |" -ForegroundColor DarkYellow
Write-Host "  |                                                           |" -ForegroundColor DarkYellow
Write-Host "  ============================================================" -ForegroundColor DarkYellow
Write-Host ""

# Create logs directory
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
}

# Task Names
$StartupTaskName = "$AppName`_AutoStart"
$RestartTaskName = "$AppName`_MidnightRestart"
$MonitorTaskName = "$AppName`_Monitor"

function Get-ServiceStatus {
    Write-Info "Checking service status..."
    Write-Host ""
    
    $startupTask = Get-ScheduledTask -TaskName $StartupTaskName -ErrorAction SilentlyContinue
    $restartTask = Get-ScheduledTask -TaskName $RestartTaskName -ErrorAction SilentlyContinue
    $monitorTask = Get-ScheduledTask -TaskName $MonitorTaskName -ErrorAction SilentlyContinue
    
    Write-Host "  Service Configuration:" -ForegroundColor Yellow
    Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray
    
    # Auto-Start Status
    Write-Host "  Auto-Start on Boot:      " -NoNewline
    if ($startupTask) {
        if ($startupTask.State -eq 'Ready') {
            Write-Success "[OK] Enabled"
        } else {
            Write-Warning "(!) $($startupTask.State)"
        }
    } else {
        Write-Host "[X] Not Configured" -ForegroundColor Red
    }
    
    # Midnight Restart Status
    Write-Host "  Midnight Restart:        " -NoNewline
    if ($restartTask) {
        if ($restartTask.State -eq 'Ready') {
            Write-Success "[OK] Enabled (12:00 AM daily)"
        } else {
            Write-Warning "(!) $($restartTask.State)"
        }
    } else {
        Write-Host "[X] Not Configured" -ForegroundColor Red
    }
    
    # Monitor Status
    Write-Host "  Health Monitor:          " -NoNewline
    if ($monitorTask) {
        if ($monitorTask.State -eq 'Ready') {
            Write-Success "[OK] Enabled (every 3 min)"
        } else {
            Write-Warning "(!) $($monitorTask.State)"
        }
    } else {
        Write-Host "[X] Not Configured" -ForegroundColor Red
    }
    
    Write-Host ""
    
    # Check if servers are running
    Write-Host "  Running Processes:" -ForegroundColor Yellow
    Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray
    
    $pythonProcs = Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*server.main*" }
    $nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue
    
    Write-Host "  Backend Server (Python):  " -NoNewline
    if ($pythonProcs) {
        Write-Success "[OK] Running (PID: $(($pythonProcs | ForEach-Object { $_.ProcessId }) -join ', '))"
    } else {
        Write-Host "[X] Not Running" -ForegroundColor Red
    }
    
    Write-Host "  Frontend Server (Node):   " -NoNewline
    if ($nodeProcs) {
        Write-Success "[OK] Running (PID: $($nodeProcs.Id -join ', '))"
    } else {
        Write-Host "[X] Not Running" -ForegroundColor Red
    }
    
    Write-Host ""
}

function Install-Services {
    Write-Info "Installing AK Legal Vault services..."
    Write-Host ""
    
    # Resolve full paths so SYSTEM (at boot) can run without PATH
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    # Prefer npm.cmd over npm.ps1 - Start-Process with .ps1 opens in Notepad instead of executing
    $npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
    $NpmCmd = if ($npmPath -match '\.ps1$') { $npmPath -replace '\.ps1$', '.cmd' } else { $npmPath }
    if (-not $PythonExe) {
        Write-Error "Python not found in PATH. Install Python and ensure it's in PATH, then run this script again."
        exit 1
    }
    if (-not $NpmCmd) {
        Write-Error "npm not found in PATH. Install Node.js and ensure it's in PATH, then run this script again."
        exit 1
    }
    Write-Info "  Python: $PythonExe"
    Write-Info "  npm:   $NpmCmd"
    Write-Host ""
    
    $PythonExeEscaped = $PythonExe.Replace("'", "''")
    $NpmCmdEscaped = $NpmCmd.Replace("'", "''")
    
    # Create startup script from template (avoids inline string parsing issues)
    $startupScriptPath = Join-Path $AppPath "service_startup.ps1"
    $startupScript = (Get-Content (Join-Path $AppPath "scripts\service_startup_template.ps1") -Raw).Replace('APPPATH', $AppPath).Replace('LOGPATH', $LogPath).Replace('PYTHONEXE', $PythonExeEscaped).Replace('NPMCMD', $NpmCmdEscaped).Replace('STARTUPDELAY', $StartupDelay)
    Set-Content -Path $startupScriptPath -Value $startupScript -Force
    
    # Create restart script from template
    $restartScriptPath = Join-Path $AppPath "service_restart.ps1"
    $restartScript = (Get-Content (Join-Path $AppPath "scripts\service_restart_template.ps1") -Raw).Replace('APPPATH', $AppPath).Replace('LOGPATH', $LogPath).Replace('STARTUPSCRIPTPATH', $startupScriptPath)
    Set-Content -Path $restartScriptPath -Value $restartScript -Force
    
    # Create monitor script from template
    $monitorScriptPath = Join-Path $AppPath "service_monitor.ps1"
    $monitorScript = (Get-Content (Join-Path $AppPath "scripts\service_monitor_template.ps1") -Raw).Replace('APPPATH', $AppPath).Replace('LOGPATH', $LogPath).Replace('RESTARTSCRIPTPATH', $restartScriptPath)
    Set-Content -Path $monitorScriptPath -Value $monitorScript -Force
    
    Write-Info "Creating scheduled tasks..."
    
    # Remove existing tasks
    Unregister-ScheduledTask -TaskName $StartupTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $RestartTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $MonitorTaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Create Auto-Start Task - default: At boot (if PC is on, system is on)
    $startupAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startupScriptPath`""
    if ($AtLogon) {
        $startupTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $startupPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
        $startupDesc = "Starts AK Legal Vault when user logs in"
    } else {
        $startupTrigger = New-ScheduledTaskTrigger -AtStartup
        $startupPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        $startupDesc = "Starts AK Legal Vault when Windows boots"
    }
    $startupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    Register-ScheduledTask -TaskName $StartupTaskName -Action $startupAction -Trigger $startupTrigger -Settings $startupSettings -Principal $startupPrincipal -Description $startupDesc -Force | Out-Null
    Write-Success "  [OK] Auto-start task created"
    
    # Create Midnight Restart Task
    $restartAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$restartScriptPath`""
    $restartTrigger = New-ScheduledTaskTrigger -Daily -At "12:00 AM"
    $restartSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $restartPrincipal = if ($AtLogon) { New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited } else { New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest }
    
    Register-ScheduledTask -TaskName $RestartTaskName -Action $restartAction -Trigger $restartTrigger -Settings $restartSettings -Principal $restartPrincipal -Description "Restarts AK Legal Vault daily at midnight" -Force | Out-Null
    Write-Success "  [OK] Midnight restart task created"
    
    # Create Health Monitor Task (every 3 minutes - faster recovery)
    $monitorAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$monitorScriptPath`""
    $monitorTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration (New-TimeSpan -Days 365)
    $monitorSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $monitorPrincipal = if ($AtLogon) { New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited } else { New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest }
    
    Register-ScheduledTask -TaskName $MonitorTaskName -Action $monitorAction -Trigger $monitorTrigger -Settings $monitorSettings -Principal $monitorPrincipal -Description "Monitors AK Legal Vault health and auto-recovers" -Force | Out-Null
    Write-Success "  [OK] Health monitor task created"
    
    Write-Host ""
    Write-Success "Installation complete!"
    Write-Host ""
    Write-Host "  The system is now configured to:" -ForegroundColor Cyan
    if ($AtLogon) {
        Write-Host "    - Start when you log in" -ForegroundColor White
    } else {
        Write-Host "    - Start when Windows boots (if PC is on, system is on)" -ForegroundColor White
    }
    Write-Host "    - Restart every night at midnight" -ForegroundColor White
    Write-Host "    - Auto-recover if services crash (every 3 min)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Note: Use -AtLogon to start only when you log in" -ForegroundColor DarkGray
    Write-Host ""
    
    # Start services now
    $startNow = Read-Host "  Would you like to start the services now? (Y/n)"
    if ($startNow -ne 'n' -and $startNow -ne 'N') {
        Write-Info "Starting services..."
        & powershell.exe -ExecutionPolicy Bypass -File $startupScriptPath
        Write-Success "  Services started!"
    }
}

function Uninstall-Services {
    Write-Warning "Uninstalling AK Legal Vault services..."
    Write-Host ""
    
    # Stop running processes (use Win32_Process - CommandLine not on Get-Process)
    Write-Info "Stopping running processes..."
    Get-CimInstance Win32_Process -Filter "name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*server.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -Filter "name='node.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*vite*' -or $_.CommandLine -like '*npm*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    
    # Remove scheduled tasks
    Write-Info "Removing scheduled tasks..."
    Unregister-ScheduledTask -TaskName $StartupTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $RestartTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $MonitorTaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Remove scripts
    Write-Info "Removing service scripts..."
    Remove-Item -Path (Join-Path $AppPath "service_startup.ps1") -Force -ErrorAction SilentlyContinue
    Remove-Item -Path (Join-Path $AppPath "service_restart.ps1") -Force -ErrorAction SilentlyContinue
    Remove-Item -Path (Join-Path $AppPath "service_monitor.ps1") -Force -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Success "Uninstallation complete!"
    Write-Host "  The system will no longer auto-start or auto-restart." -ForegroundColor Yellow
    Write-Host ""
}

# Main execution
if ($Status) {
    Get-ServiceStatus
} elseif ($Uninstall) {
    Uninstall-Services
} else {
    # Show current status first
    Get-ServiceStatus
    
    $existingTasks = Get-ScheduledTask -TaskName "$AppName*" -ErrorAction SilentlyContinue
    if ($existingTasks) {
        Write-Warning "Services are already configured."
        $choice = Read-Host "  Would you like to reinstall? (Y/n)"
        if ($choice -eq 'n' -or $choice -eq 'N') {
            exit
        }
    }
    
    Install-Services
}

Write-Host ""
Write-Host "  ---------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Powered by LexTech Systems" -ForegroundColor DarkGray
Write-Host ""

