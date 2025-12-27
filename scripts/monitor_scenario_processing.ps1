# Monitor Scenario Processing Progress
# Shows real-time progress of batch scenario processing

$progressFile = "data\scenarios\.processed_cases.json"
$dbPath = "data\scenario_db"

Write-Host "Scenario Processing Monitor" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Gray
Write-Host ""

while ($true) {
    Clear-Host
    Write-Host "Scenario Processing Monitor" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Gray
    Write-Host ""
    
    # Check if progress file exists
    if (Test-Path $progressFile) {
        try {
            $progress = Get-Content $progressFile -Raw | ConvertFrom-Json
            
            # Basic stats
            Write-Host "Processing Status:" -ForegroundColor Yellow
            Write-Host ("  Total Processed: {0:N0}" -f $progress.total_processed) -ForegroundColor Green
            Write-Host ("  Last Update: {0}" -f $progress.last_update) -ForegroundColor Gray
            Write-Host ""
            
            # Progress info if available
            if ($progress.progress) {
                $p = $progress.progress
                Write-Host "Progress:" -ForegroundColor Yellow
                Write-Host ("  Completion: {0:F1}%" -f $p.progress_percent) -ForegroundColor Cyan
                Write-Host ("  Attempted: {0:N0} / {1:N0}" -f $p.total_attempted, $p.total_to_process) -ForegroundColor White
                Write-Host ("  Successful: {0:N0}" -f $p.total_processed) -ForegroundColor Green
                Write-Host ("  Failed: {0:N0}" -f $p.total_failed) -ForegroundColor $(if ($p.total_failed -gt 0) { "Red" } else { "Gray" })
                Write-Host ("  Current Batch: {0}" -f $p.current_batch) -ForegroundColor Gray
                Write-Host ""
                
                # Progress bar
                $barWidth = 50
                $filled = [math]::Floor($p.progress_percent / 100 * $barWidth)
                $bar = ("█" * $filled) + ("░" * ($barWidth - $filled))
                Write-Host "  [$bar] $($p.progress_percent.ToString('F1'))%" -ForegroundColor Green
                Write-Host ""
            }
            
            # Stats
            if ($progress.stats) {
                $stats = $progress.stats
                Write-Host "Statistics:" -ForegroundColor Yellow
                Write-Host ("  Processed: {0:N0}" -f $stats.processed) -ForegroundColor Green
                Write-Host ("  Failed: {0:N0}" -f $stats.failed) -ForegroundColor $(if ($stats.failed -gt 0) { "Red" } else { "Gray" })
                Write-Host ("  Skipped: {0:N0}" -f $stats.skipped) -ForegroundColor Gray
                Write-Host ""
                
                # Outcome distribution
                if ($stats.outcomes) {
                    Write-Host "Outcome Distribution:" -ForegroundColor Yellow
                    $outcomes = $stats.outcomes.PSObject.Properties | Sort-Object Value -Descending
                    foreach ($outcome in $outcomes) {
                        $count = $outcome.Value
                        $pct = if ($stats.processed -gt 0) { ($count / $stats.processed * 100).ToString("F1") } else { "0.0" }
                        Write-Host ("  {0}: {1:N0} ({2}%)" -f $outcome.Name, $count, $pct) -ForegroundColor White
                    }
                    Write-Host ""
                }
            }
            
        } catch {
            Write-Host "Error reading progress file: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "Progress file not found. Processing may not have started yet." -ForegroundColor Yellow
        Write-Host ""
    }
    
    # Check database size
    if (Test-Path $dbPath) {
        $dbSize = (Get-ChildItem $dbPath -Recurse -ErrorAction SilentlyContinue | 
                   Measure-Object -Property Length -Sum).Sum / 1MB
        Write-Host "Database:" -ForegroundColor Yellow
        Write-Host ("  Size: {0:F2} MB" -f $dbSize) -ForegroundColor Gray
        Write-Host ""
    }
    
    # Get scenario count if possible
    try {
        $scenarioCount = python -c "import sys; sys.path.insert(0, '.'); from server.services.scenario_service import scenario_service; scenario_service._ensure_initialized(); stats = scenario_service.get_collection_stats(); print(stats.get('total_scenarios', 0))" 2>$null
        if ($scenarioCount) {
            Write-Host "Scenario Database:" -ForegroundColor Yellow
            Write-Host ("  Total Scenarios: {0:N0}" -f [int]$scenarioCount) -ForegroundColor Green
            Write-Host ""
        }
    } catch {
        # Ignore errors
    }
    
    Write-Host ("=" * 60) -ForegroundColor Gray
    Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Gray
    Write-Host ""
    
    Start-Sleep -Seconds 2
}

