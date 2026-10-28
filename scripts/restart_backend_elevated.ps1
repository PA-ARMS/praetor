#Requires -RunAsAdministrator
<#
  Kill listeners on port 5001, then start the FastAPI backend in a new window.
  Use when the backend runs as SYSTEM (scheduled task) and normal taskkill fails.
#>
param([int]$Port = 5001)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$pids = [System.Collections.Generic.HashSet[int]]::new()
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    [void]$pids.Add($_.OwningProcess)
}
foreach ($procId in $pids) {
    if ($procId -le 0) { continue }
    Write-Host "taskkill /F /PID $procId (port $Port)"
    & cmd.exe /c "taskkill /F /PID $procId" 2>&1 | Out-Host
}
Start-Sleep -Seconds 2

$env:PYTHONPATH = $root
$arg = "/k cd /d `"$root`" && set PYTHONPATH=$root && python -m uvicorn server.main:app --host 0.0.0.0 --port $Port --timeout-keep-alive 600"
Start-Process cmd.exe -ArgumentList $arg -WorkingDirectory $root
Write-Host "Started backend in new window on port $Port"
