# Set Static IP Address for Virginia Legal AI Server
# Run as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Virginia Legal AI - Static IP Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

# Get WiFi network adapter (prefer WiFi over Ethernet)
# WiFi adapters have MediaType = 9 (IEEE 802.11) or contain "Wireless" or "Wi-Fi" in name/description
$wifiAdapter = Get-NetAdapter | Where-Object {
    $_.Status -eq "Up" -and (
        $_.MediaType -eq 9 -or 
        $_.Name -like "*Wi-Fi*" -or 
        $_.Name -like "*Wireless*" -or
        $_.InterfaceDescription -like "*Wireless*" -or
        $_.InterfaceDescription -like "*Wi-Fi*" -or
        $_.InterfaceDescription -like "*802.11*"
    )
} | Select-Object -First 1

# If no WiFi adapter found, try any active adapter as fallback
if (-not $wifiAdapter) {
    Write-Host "WARNING: No active WiFi adapter found!" -ForegroundColor Yellow
    Write-Host "Attempting to use any active network adapter..." -ForegroundColor Yellow
    Write-Host ""
    $wifiAdapter = Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -First 1
}

if (-not $wifiAdapter) {
    Write-Host "ERROR: No active network adapter found!" -ForegroundColor Red
    pause
    exit 1
}

# Check if the selected adapter is actually WiFi
$isWiFi = ($wifiAdapter.MediaType -eq 9 -or 
           $wifiAdapter.Name -like "*Wi-Fi*" -or 
           $wifiAdapter.Name -like "*Wireless*" -or
           $wifiAdapter.InterfaceDescription -like "*Wireless*" -or
           $wifiAdapter.InterfaceDescription -like "*Wi-Fi*" -or
           $wifiAdapter.InterfaceDescription -like "*802.11*")

if ($isWiFi) {
    Write-Host "WiFi Network Adapter Selected: $($wifiAdapter.Name)" -ForegroundColor Green
    Write-Host "Interface: $($wifiAdapter.InterfaceDescription)" -ForegroundColor Cyan
} else {
    Write-Host "Network Adapter Selected: $($wifiAdapter.Name)" -ForegroundColor Yellow
    Write-Host "Interface: $($wifiAdapter.InterfaceDescription)" -ForegroundColor Yellow
    Write-Host "(Note: This is not a WiFi adapter)" -ForegroundColor Yellow
}
Write-Host ""

# Get current IP configuration
$currentIP = Get-NetIPAddress -InterfaceIndex $wifiAdapter.InterfaceIndex -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}
if ($currentIP) {
    Write-Host "Current IP: $($currentIP.IPAddress)" -ForegroundColor Yellow
    Write-Host "Current Gateway: $((Get-NetRoute -InterfaceIndex $wifiAdapter.InterfaceIndex -DestinationPrefix "0.0.0.0/0").NextHop)" -ForegroundColor Yellow
    Write-Host ""
}

# Get input
Write-Host "Enter static IP configuration:" -ForegroundColor Cyan
$staticIP = Read-Host "IP Address (e.g., 192.168.1.100)"
$subnetMask = Read-Host "Subnet Mask (default: 255.255.255.0)"
if ([string]::IsNullOrEmpty($subnetMask)) { $subnetMask = "255.255.255.0" }

$gateway = Read-Host "Gateway (default: 192.168.1.1)"
if ([string]::IsNullOrEmpty($gateway)) { $gateway = "192.168.1.1" }

$dns1 = Read-Host "DNS Server 1 (default: 192.168.1.1)"
if ([string]::IsNullOrEmpty($dns1)) { $dns1 = "192.168.1.1" }

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  IP: $staticIP" -ForegroundColor White
Write-Host "  Subnet: $subnetMask" -ForegroundColor White
Write-Host "  Gateway: $gateway" -ForegroundColor White
Write-Host "  DNS: $dns1" -ForegroundColor White
Write-Host ""

$confirm = Read-Host "Apply this configuration? (Y/N)"
if ($confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

try {
    # Remove existing IP configuration
    Remove-NetIPAddress -InterfaceIndex $wifiAdapter.InterfaceIndex -Confirm:$false -ErrorAction SilentlyContinue
    
    # Set static IP
    New-NetIPAddress -InterfaceIndex $wifiAdapter.InterfaceIndex -IPAddress $staticIP -PrefixLength 24 -DefaultGateway $gateway
    
    # Set DNS
    Set-DnsClientServerAddress -InterfaceIndex $wifiAdapter.InterfaceIndex -ServerAddresses $dns1
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Static IP Configured Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "New IP Address: $staticIP" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Update your network access URL to:" -ForegroundColor Yellow
    Write-Host "  http://$staticIP`:3000" -ForegroundColor Green
    Write-Host ""
    Write-Host "Or use hostname:" -ForegroundColor Yellow
    Write-Host "  http://$env:COMPUTERNAME`:3000" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to configure static IP" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "You may need to configure this manually in:" -ForegroundColor Yellow
    Write-Host "  Network Settings > Adapter Properties > TCP/IPv4" -ForegroundColor White
}

pause

