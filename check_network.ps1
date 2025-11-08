# Check Network Configuration

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Network Configuration Check" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Get all IPv4 addresses
Write-Host "All IPv4 Addresses:" -ForegroundColor Yellow
Write-Host ""

Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object {
    $status = "OK"
    $note = ""
    
    if ($_.IPAddress -like "127.*") {
        $status = "SKIP"
        $note = "(Loopback)"
    } elseif ($_.IPAddress -like "169.254.*") {
        $status = "WARN"
        $note = "(APIPA - No DHCP)"
    } elseif ($_.InterfaceAlias -like "*Loopback*") {
        $status = "SKIP"
        $note = "(Loopback)"
    } elseif ($_.InterfaceAlias -like "*Virtual*" -or $_.InterfaceAlias -like "*VMware*") {
        $status = "SKIP"
        $note = "(Virtual Adapter)"
    } else {
        $status = "GOOD"
        $note = "(Valid LAN IP)"
    }
    
    $color = switch ($status) {
        "GOOD" { "Green" }
        "OK" { "White" }
        "WARN" { "Yellow" }
        "SKIP" { "Gray" }
    }
    
    Write-Host "[$status] " -ForegroundColor $color -NoNewline
    Write-Host "$($_.IPAddress) " -NoNewline
    Write-Host "- $($_.InterfaceAlias) " -ForegroundColor Cyan -NoNewline
    Write-Host "$note" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Recommend the best IP
$bestIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and 
    $_.IPAddress -notlike "169.254.*" -and
    $_.InterfaceAlias -notlike "*Loopback*" -and
    $_.InterfaceAlias -notlike "*Virtual*" -and
    $_.InterfaceAlias -notlike "*VMware*"
} | Select-Object -First 1).IPAddress

if ($bestIP) {
    Write-Host "Recommended IP for LAN access: " -ForegroundColor Green -NoNewline
    Write-Host "$bestIP" -ForegroundColor White
    Write-Host ""
    Write-Host "Use this URL for network access:" -ForegroundColor Yellow
    Write-Host "  http://${bestIP}:8503/?uid=<JUDGE_UID>" -ForegroundColor White
} else {
    Write-Host "WARNING: No valid LAN IP found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possible reasons:" -ForegroundColor Yellow
    Write-Host "  1. Not connected to network" -ForegroundColor White
    Write-Host "  2. DHCP not available (showing 169.254.x.x)" -ForegroundColor White
    Write-Host "  3. Network adapter disabled" -ForegroundColor White
    Write-Host ""
    Write-Host "Solutions:" -ForegroundColor Yellow
    Write-Host "  1. Check network cable/WiFi connection" -ForegroundColor White
    Write-Host "  2. Run: ipconfig /renew" -ForegroundColor White
    Write-Host "  3. Restart network adapter" -ForegroundColor White
    Write-Host ""
    Write-Host "For local testing only, use:" -ForegroundColor Yellow
    Write-Host "  http://localhost:8503/?uid=<JUDGE_UID>" -ForegroundColor White
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

