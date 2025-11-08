# Compare Mode - Export All Data

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Compare Mode - Export Data" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check database
if (-not (Test-Path "aiv_compare_v1.db")) {
    Write-Host "[ERROR] Database not found!" -ForegroundColor Red
    exit
}

Write-Host "Starting export..." -ForegroundColor Yellow
Write-Host ""

# Run export script
python scripts\export_ratings_compare.py

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Export Completed" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Export directory: export_results_compare\" -ForegroundColor Yellow
Write-Host ""

