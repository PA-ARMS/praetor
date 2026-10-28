#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets a static IP address on the primary network adapter so the PC keeps the same IP on the local network.
.DESCRIPTION
    Configures the active network adapter (Wi-Fi or Ethernet) with a static IP.
    Uses current IP, gateway, and DNS - run once to "lock in" your current configuration.
    Requires Administrator privileges.
.EXAMPLE
    .\scripts\set_static_ip.ps1
    .\scripts\set_static_ip.ps1 -StaticIP 192.168.1.53
#>
param(
    [string]$StaticIP = "",
    [string]$Gateway = "192.168.1.1",
    [string]$PrefixLength = "24",  # 24 = 255.255.255.0
    [string[]]$DnsServers = @("192.168.1.1", "8.8.8.8")
)

$ErrorActionPreference = "Stop"

# Find the active adapter (the one with a default gateway)
$adapter = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null } | Select-Object -First 1
if (-not $adapter) {
    Write-Host "ERROR: No active network adapter with default gateway found." -ForegroundColor Red
    exit 1
}

$interfaceAlias = $adapter.InterfaceAlias
$currentIP = ($adapter.IPv4Address.IPAddress) | Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($StaticIP)) {
    $StaticIP = $currentIP
    Write-Host "Using current IP: $StaticIP" -ForegroundColor Cyan
}

# Get current gateway if not specified
$currentGateway = ($adapter.IPv4DefaultGateway.NextHop) | Select-Object -First 1
if ($Gateway -eq "192.168.1.1" -and $currentGateway) {
    $Gateway = $currentGateway
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Static IP Configuration" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Adapter:    $interfaceAlias"
Write-Host "  Static IP:  $StaticIP"
Write-Host "  Gateway:    $Gateway"
Write-Host "  Subnet:     /$PrefixLength (255.255.255.0)"
Write-Host "  DNS:       $($DnsServers -join ', ')"
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Apply this configuration? (y/n)"
if ($confirm -ne 'y' -and $confirm -ne 'Y') {
    Write-Host "Cancelled." -ForegroundColor Gray
    exit 0
}

try {
    # Remove existing IP configuration (switches from DHCP to manual)
    Remove-NetIPAddress -InterfaceAlias $interfaceAlias -Confirm:$false -ErrorAction SilentlyContinue
    
    # Set static IP
    New-NetIPAddress -InterfaceAlias $interfaceAlias -IPAddress $StaticIP -PrefixLength $PrefixLength -DefaultGateway $Gateway
    
    # Set DNS servers
    Set-DnsClientServerAddress -InterfaceAlias $interfaceAlias -ServerAddresses $DnsServers
    
    Write-Host ""
    Write-Host "SUCCESS: Static IP configured." -ForegroundColor Green
    Write-Host "  Your PC will now use $StaticIP on the network." -ForegroundColor Green
    Write-Host ""
    Write-Host "If CORS in .env uses this IP, no changes needed." -ForegroundColor Cyan
    Write-Host "Access the app at: http://${StaticIP}:3000" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
