# Kill process using specified port.
# Uses netstat fallback when Get-NetTCPConnection fails (e.g. "paging file too small" under memory load).
param([int]$Port = 5001)

function Stop-ProcessHard {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return $false }
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        return $true
    } catch {
        # Same-user processes; SYSTEM/Session 0 still need Admin + taskkill (see STOP_BACKEND_ADMIN.bat)
        $null = & cmd.exe /c "taskkill /F /PID $ProcessId" 2>&1
        return ($LASTEXITCODE -eq 0)
    }
}

$pidsToKill = [System.Collections.Generic.HashSet[int]]::new()

try {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | ForEach-Object {
        [void]$pidsToKill.Add($_.OwningProcess)
    }
} catch {
    $out = & cmd.exe /c "netstat -ano 2>nul"
    foreach ($l in $out) {
        if ($l -match ":${Port}\s+.*LISTENING\s+(\d+)\s*$") {
            [void]$pidsToKill.Add([int]$Matches[1])
        }
    }
}

foreach ($procId in $pidsToKill) {
    if ($procId -eq 0) { continue }
    if (Stop-ProcessHard -ProcessId $procId) {
        Write-Host "Stopped PID $procId on port $Port"
        continue
    }
    $sess = $null
    try { $sess = (Get-Process -Id $procId -ErrorAction Stop).SessionId } catch {}
    Write-Host "Could not stop PID $procId (port $Port)." -ForegroundColor Yellow
    if ($sess -eq 0) {
        Write-Host "  Reason: Process is in Session 0 (typical for services / SYSTEM), or you lack permission to terminate it."
        Write-Host "  Fix: Right-click STOP_BACKEND_ADMIN.bat -> Run as administrator, or end the scheduled task process as SYSTEM."
    } else {
        Write-Host "  Try: Close the app window, or run STOP_BACKEND_ADMIN.bat as Administrator."
    }
}
