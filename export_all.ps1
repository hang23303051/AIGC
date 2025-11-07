# Export Rating Data Script

$ErrorActionPreference = "Stop"
$pythonExe = "D:\miniconda3\envs\learn\python.exe"
$dbFile = "aiv_eval_v4.db"
$outputDir = "export_results"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Rating Data Export Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check database exists
if (-not (Test-Path $dbFile)) {
    Write-Host "`n[ERROR] Database not found: $dbFile" -ForegroundColor Red
    Write-Host "Please prepare data first" -ForegroundColor Yellow
    exit 1
}

# Create output directory
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

# Set environment variable for large scale
$env:AIV_DATA_SCALE = 'large'

# Step 1: Check progress
Write-Host "`n[1/4] Checking progress..." -ForegroundColor Yellow
& $pythonExe check_progress.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] Progress check failed, continuing anyway..." -ForegroundColor Yellow
}

# Step 2: Export wide format
Write-Host "`n[2/4] Exporting wide format (5 models)..." -ForegroundColor Yellow
$wideFile = "$outputDir\ratings_wide_$timestamp.csv"
& $pythonExe scripts\export_ratings.py --db $dbFile --out $wideFile --format wide
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Wide format exported to: $wideFile" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Wide format export failed" -ForegroundColor Red
}

# Step 3: Export long format
Write-Host "`n[3/4] Exporting long format..." -ForegroundColor Yellow
$longFile = "$outputDir\ratings_long_$timestamp.csv"
& $pythonExe scripts\export_ratings.py --db $dbFile --out $longFile --format long
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Long format exported to: $longFile" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Long format export failed" -ForegroundColor Red
}

# Step 4: Create summary
Write-Host "`n[4/4] Creating summary..." -ForegroundColor Yellow
$summaryFile = "$outputDir\summary_$timestamp.txt"
& $pythonExe check_progress.py > $summaryFile 2>&1
Write-Host "  [OK] Summary saved to: $summaryFile" -ForegroundColor Green

# Final summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Export Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nExported files:" -ForegroundColor Yellow
Write-Host "  Wide format:  $wideFile" -ForegroundColor White
Write-Host "  Long format:  $longFile" -ForegroundColor White
Write-Host "  Summary:      $summaryFile" -ForegroundColor White

Write-Host "`nOutput directory: $outputDir" -ForegroundColor Cyan
Write-Host "`nData configuration:" -ForegroundColor Yellow
Write-Host "  Models: 5 (wan21, vidu, cogfun, cogvideo5b, videocrafter)" -ForegroundColor Gray
Write-Host "  Samples: 1000+" -ForegroundColor Gray

Write-Host ""

