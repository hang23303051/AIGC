# AI Video Evaluation System - Status Check

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Service Status Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Get local IP
function Get-LocalIP {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | 
               Where-Object {$_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.254.*"} | 
               Select-Object -First 1).IPAddress
        return $ip
    } catch {
        return "127.0.0.1"
    }
}

$localIP = Get-LocalIP

Write-Host ""
Write-Host "[Network Info]" -ForegroundColor Yellow
Write-Host "  Local IP: $localIP" -ForegroundColor Green

# Check port 8010
Write-Host ""
Write-Host "[1] Video Service (port 8010):" -ForegroundColor Yellow
$port8010 = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if ($port8010) {
    Write-Host "  [OK] Running (PID: $($port8010.OwningProcess))" -ForegroundColor Green
    Write-Host "      URL: http://${localIP}:8010" -ForegroundColor Cyan
} else {
    Write-Host "  [X] Not running" -ForegroundColor Red
}

# Check port 8502
Write-Host ""
Write-Host "[2] Web UI (port 8502):" -ForegroundColor Yellow
$port8502 = Get-NetTCPConnection -LocalPort 8502 -State Listen -ErrorAction SilentlyContinue
if ($port8502) {
    Write-Host "  [OK] Running (PID: $($port8502.OwningProcess))" -ForegroundColor Green
    Write-Host "      URL: http://${localIP}:8502" -ForegroundColor Cyan
} else {
    Write-Host "  [X] Not running" -ForegroundColor Red
}

# Check firewall
Write-Host ""
Write-Host "[3] Firewall Rules:" -ForegroundColor Yellow
$firewallRules = Get-NetFirewallRule -DisplayName "AIV-*" -ErrorAction SilentlyContinue
if ($firewallRules) {
    Write-Host "  [OK] Configured" -ForegroundColor Green
    foreach ($rule in $firewallRules) {
        Write-Host "      - $($rule.DisplayName) [$($rule.Enabled)]" -ForegroundColor Gray
    }
} else {
    Write-Host "  [WARN] Not configured (LAN access may fail)" -ForegroundColor Yellow
    Write-Host "      Run: .\scripts\setup_firewall.ps1 (as admin)" -ForegroundColor Cyan
}

# Check database
Write-Host ""
Write-Host "[4] Database:" -ForegroundColor Yellow
$dbPath = "aiv_eval_v4_round2.db"
if (Test-Path $dbPath) {
    $dbSize = (Get-Item $dbPath).Length / 1KB
    Write-Host "  [OK] Exists (size: $([math]::Round($dbSize, 2)) KB)" -ForegroundColor Green
} else {
    Write-Host "  [X] Not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($port8010 -and $port8502) {
    Write-Host "  System Running Normally!" -ForegroundColor Green
} else {
    Write-Host "  Some Services Not Running" -ForegroundColor Yellow
    Write-Host "  Run: .\lan_start.ps1" -ForegroundColor Cyan
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

