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
    [switch]$Status
)

$ErrorActionPreference = "Stop"

# Configuration
$AppName = "AKLegalVault"
$AppDisplayName = "AK Legal Vault"
$AppPath = $PSScriptRoot
$LogPath = Join-Path $AppPath "logs"
$StartupDelay = 30  # Seconds to wait after boot before starting

# Colors for console output
function Write-Success { Write-Host $args[0] -ForegroundColor Green }
function Write-Info { Write-Host $args[0] -ForegroundColor Cyan }
function Write-Warning { Write-Host $args[0] -ForegroundColor Yellow }
function Write-Error { Write-Host $args[0] -ForegroundColor Red }

# Header
Clear-Host
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor DarkYellow
Write-Host "  ║                                                           ║" -ForegroundColor DarkYellow
Write-Host "  ║           " -NoNewline -ForegroundColor DarkYellow
Write-Host "AK LEGAL VAULT" -NoNewline -ForegroundColor Yellow
Write-Host "                              ║" -ForegroundColor DarkYellow
Write-Host "  ║           " -NoNewline -ForegroundColor DarkYellow
Write-Host "Service Management System" -NoNewline -ForegroundColor White
Write-Host "                    ║" -ForegroundColor DarkYellow
Write-Host "  ║                                                           ║" -ForegroundColor DarkYellow
Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor DarkYellow
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
    Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    
    # Auto-Start Status
    Write-Host "  Auto-Start on Boot:      " -NoNewline
    if ($startupTask) {
        if ($startupTask.State -eq 'Ready') {
            Write-Success "✓ Enabled"
        } else {
            Write-Warning "⚠ $($startupTask.State)"
        }
    } else {
        Write-Host "✗ Not Configured" -ForegroundColor Red
    }
    
    # Midnight Restart Status
    Write-Host "  Midnight Restart:        " -NoNewline
    if ($restartTask) {
        if ($restartTask.State -eq 'Ready') {
            Write-Success "✓ Enabled (12:00 AM daily)"
        } else {
            Write-Warning "⚠ $($restartTask.State)"
        }
    } else {
        Write-Host "✗ Not Configured" -ForegroundColor Red
    }
    
    # Monitor Status
    Write-Host "  Health Monitor:          " -NoNewline
    if ($monitorTask) {
        if ($monitorTask.State -eq 'Ready') {
            Write-Success "✓ Enabled (every 5 min)"
        } else {
            Write-Warning "⚠ $($monitorTask.State)"
        }
    } else {
        Write-Host "✗ Not Configured" -ForegroundColor Red
    }
    
    Write-Host ""
    
    # Check if servers are running
    Write-Host "  Running Processes:" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    
    $pythonProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*server.main*" }
    $nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue
    
    Write-Host "  Backend Server (Python):  " -NoNewline
    if ($pythonProcs) {
        Write-Success "✓ Running (PID: $($pythonProcs.Id -join ', '))"
    } else {
        Write-Host "✗ Not Running" -ForegroundColor Red
    }
    
    Write-Host "  Frontend Server (Node):   " -NoNewline
    if ($nodeProcs) {
        Write-Success "✓ Running (PID: $($nodeProcs.Id -join ', '))"
    } else {
        Write-Host "✗ Not Running" -ForegroundColor Red
    }
    
    Write-Host ""
}

function Install-Services {
    Write-Info "Installing AK Legal Vault services..."
    Write-Host ""
    
    # Create startup script
    $startupScript = @"
# AK Legal Vault - Startup Script
`$ErrorActionPreference = 'SilentlyContinue'
`$AppPath = '$AppPath'
`$LogPath = '$LogPath'

# Log function
function Write-Log {
    param([string]`$Message)
    `$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path `$LogPath 'service.log') -Value "[`$timestamp] `$Message"
}

Write-Log "Starting AK Legal Vault..."

# Wait for system to stabilize
Start-Sleep -Seconds $StartupDelay

# Set working directory
Set-Location `$AppPath

# Set environment
`$env:PYTHONPATH = `$AppPath
`$env:SCENARIO_DB_ENABLED = 'True'

# Start backend
Write-Log "Starting backend server..."
Start-Process -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'server.main:app', '--host', '0.0.0.0', '--port', '5000', '--timeout-keep-alive', '600' -WindowStyle Hidden -WorkingDirectory `$AppPath

Start-Sleep -Seconds 5

# Start frontend
Write-Log "Starting frontend server..."
Set-Location (Join-Path `$AppPath 'client')
Start-Process -FilePath 'npm' -ArgumentList 'run', 'dev' -WindowStyle Hidden -WorkingDirectory (Join-Path `$AppPath 'client')

Write-Log "Services started successfully"
"@

    $startupScriptPath = Join-Path $AppPath "service_startup.ps1"
    Set-Content -Path $startupScriptPath -Value $startupScript -Force
    
    # Create restart script with notification
    $restartScript = @"
# AK Legal Vault - Restart Script
`$ErrorActionPreference = 'SilentlyContinue'
`$AppPath = '$AppPath'
`$LogPath = '$LogPath'

function Write-Log {
    param([string]`$Message)
    `$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path `$LogPath 'service.log') -Value "[`$timestamp] `$Message"
}

Write-Log "Scheduled restart initiated..."

# Send restart notification to connected clients (if API is available)
try {
    `$body = @{
        type = 'system_restart'
        message = 'System maintenance restart in progress. Service will resume shortly.'
        timestamp = (Get-Date -Format 'o')
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri 'http://localhost:5000/api/system/broadcast' -Method POST -Body `$body -ContentType 'application/json' -TimeoutSec 5
    Start-Sleep -Seconds 5  # Give clients time to see notification
} catch {
    Write-Log "Could not send restart notification (API may be down)"
}

# Stop existing processes gracefully
Write-Log "Stopping existing processes..."

# Stop backend (Python/uvicorn)
Get-Process -Name 'python' -ErrorAction SilentlyContinue | Where-Object { 
    `$_.CommandLine -like '*uvicorn*' -or `$_.CommandLine -like '*server.main*' 
} | ForEach-Object {
    `$_ | Stop-Process -Force
    Write-Log "Stopped Python process: `$(`$_.Id)"
}

# Stop frontend (Node)
Get-Process -Name 'node' -ErrorAction SilentlyContinue | ForEach-Object {
    `$_ | Stop-Process -Force  
    Write-Log "Stopped Node process: `$(`$_.Id)"
}

Start-Sleep -Seconds 3

# Restart services
Write-Log "Restarting services..."
& '$startupScriptPath'

Write-Log "Restart complete"
"@

    $restartScriptPath = Join-Path $AppPath "service_restart.ps1"
    Set-Content -Path $restartScriptPath -Value $restartScript -Force
    
    # Create monitor script
    $monitorScript = @"
# AK Legal Vault - Health Monitor
`$ErrorActionPreference = 'SilentlyContinue'
`$AppPath = '$AppPath'
`$LogPath = '$LogPath'

function Write-Log {
    param([string]`$Message)
    `$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path `$LogPath 'monitor.log') -Value "[`$timestamp] `$Message"
}

# Check if backend is running
`$backendRunning = `$false
try {
    `$response = Invoke-RestMethod -Uri 'http://localhost:5000/health' -TimeoutSec 10
    if (`$response.status -eq 'healthy') {
        `$backendRunning = `$true
    }
} catch {
    `$backendRunning = `$false
}

# Check if frontend is running  
`$frontendRunning = `$false
try {
    `$response = Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 10 -UseBasicParsing
    if (`$response.StatusCode -eq 200) {
        `$frontendRunning = `$true
    }
} catch {
    `$frontendRunning = `$false
}

# Restart if needed
if (-not `$backendRunning -or -not `$frontendRunning) {
    Write-Log "Service down detected - Backend: `$backendRunning, Frontend: `$frontendRunning"
    Write-Log "Initiating automatic recovery..."
    & '$restartScriptPath'
}
"@

    $monitorScriptPath = Join-Path $AppPath "service_monitor.ps1"
    Set-Content -Path $monitorScriptPath -Value $monitorScript -Force
    
    Write-Info "Creating scheduled tasks..."
    
    # Remove existing tasks
    Unregister-ScheduledTask -TaskName $StartupTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $RestartTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $MonitorTaskName -Confirm:$false -ErrorAction SilentlyContinue
    
    # Create Auto-Start Task (runs at system startup)
    $startupAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startupScriptPath`""
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $startupSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
    $startupPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    
    Register-ScheduledTask -TaskName $StartupTaskName -Action $startupAction -Trigger $startupTrigger -Settings $startupSettings -Principal $startupPrincipal -Description "Starts AK Legal Vault on system boot" -Force | Out-Null
    Write-Success "  ✓ Auto-start task created"
    
    # Create Midnight Restart Task
    $restartAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$restartScriptPath`""
    $restartTrigger = New-ScheduledTaskTrigger -Daily -At "12:00 AM"
    $restartSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $restartPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    
    Register-ScheduledTask -TaskName $RestartTaskName -Action $restartAction -Trigger $restartTrigger -Settings $restartSettings -Principal $restartPrincipal -Description "Restarts AK Legal Vault daily at midnight" -Force | Out-Null
    Write-Success "  ✓ Midnight restart task created"
    
    # Create Health Monitor Task (every 5 minutes)
    $monitorAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$monitorScriptPath`""
    $monitorTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)
    $monitorSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $monitorPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    
    Register-ScheduledTask -TaskName $MonitorTaskName -Action $monitorAction -Trigger $monitorTrigger -Settings $monitorSettings -Principal $monitorPrincipal -Description "Monitors AK Legal Vault health and auto-recovers" -Force | Out-Null
    Write-Success "  ✓ Health monitor task created"
    
    Write-Host ""
    Write-Success "Installation complete!"
    Write-Host ""
    Write-Host "  The system is now configured to:" -ForegroundColor Cyan
    Write-Host "    • Start automatically when Windows boots" -ForegroundColor White
    Write-Host "    • Restart every night at midnight" -ForegroundColor White
    Write-Host "    • Auto-recover if services crash" -ForegroundColor White
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
    
    # Stop running processes
    Write-Info "Stopping running processes..."
    Get-Process -Name 'python' -ErrorAction SilentlyContinue | Where-Object { 
        $_.CommandLine -like '*uvicorn*' -or $_.CommandLine -like '*server.main*' 
    } | Stop-Process -Force
    
    Get-Process -Name 'node' -ErrorAction SilentlyContinue | Stop-Process -Force
    
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
Write-Host "  ─────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Powered by LexTech Systems" -ForegroundColor DarkGray
Write-Host ""

