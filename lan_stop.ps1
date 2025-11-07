# AI Video Evaluation System - Stop All Services

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Stop All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Stopping services..." -ForegroundColor Yellow

# Stop port 8010
Write-Host ""
Write-Host "[1/2] Stopping video service (port 8010)..." -ForegroundColor Cyan
$port8010 = Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue
if ($port8010) {
    $pid8010 = $port8010.OwningProcess | Select-Object -First 1
    Stop-Process -Id $pid8010 -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Port 8010 released" -ForegroundColor Green
} else {
    Write-Host "  [-] Port 8010 not in use" -ForegroundColor Gray
}

# Stop port 8502
Write-Host ""
Write-Host "[2/2] Stopping web UI (port 8502)..." -ForegroundColor Cyan
$port8502 = Get-NetTCPConnection -LocalPort 8502 -ErrorAction SilentlyContinue
if ($port8502) {
    $pid8502 = $port8502.OwningProcess | Select-Object -First 1
    Stop-Process -Id $pid8502 -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] Port 8502 released" -ForegroundColor Green
} else {
    Write-Host "  [-] Port 8502 not in use" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All Services Stopped!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

# Verify ports
Write-Host ""
Write-Host "Verifying port status:" -ForegroundColor Yellow
$check8010 = Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue
$check8502 = Get-NetTCPConnection -LocalPort 8502 -ErrorAction SilentlyContinue

if (-not $check8010 -and -not $check8502) {
    Write-Host "  [OK] All ports released" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Some ports still in use" -ForegroundColor Yellow
    if ($check8010) { Write-Host "      - Port 8010 still in use" -ForegroundColor Red }
    if ($check8502) { Write-Host "      - Port 8502 still in use" -ForegroundColor Red }
}

Write-Host ""

