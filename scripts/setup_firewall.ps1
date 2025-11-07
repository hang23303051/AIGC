# Windows Firewall Setup for LAN Access
# Ports: 8010 (Video) and 8502 (UI)
# Run as Administrator

param([switch]$Remove)

Write-Host "========================================"
Write-Host "  Firewall Configuration - LAN Mode"
Write-Host "========================================"

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host ""
    Write-Host "[ERROR] Need Administrator privileges!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

$ruleName8010 = "AIV-VideoService-8010"
$ruleName8502 = "AIV-WebUI-8502"

if ($Remove) {
    Write-Host ""
    Write-Host "Removing firewall rules..." -ForegroundColor Yellow
    
    Remove-NetFirewallRule -DisplayName $ruleName8010 -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -DisplayName $ruleName8502 -ErrorAction SilentlyContinue
    
    Write-Host "  [OK] Firewall rules removed" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Adding firewall rules..." -ForegroundColor Yellow
    
    # Remove existing rules
    Remove-NetFirewallRule -DisplayName $ruleName8010 -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -DisplayName $ruleName8502 -ErrorAction SilentlyContinue
    
    # Add port 8010 rule
    New-NetFirewallRule -DisplayName $ruleName8010 -Direction Inbound -Protocol TCP -LocalPort 8010 -Action Allow -Profile Private,Domain | Out-Null
    Write-Host "  [OK] Port 8010 (Video Service)" -ForegroundColor Green
    
    # Add port 8502 rule
    New-NetFirewallRule -DisplayName $ruleName8502 -Direction Inbound -Protocol TCP -LocalPort 8502 -Action Allow -Profile Private,Domain | Out-Null
    Write-Host "  [OK] Port 8502 (Web UI)" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "[SUCCESS] Firewall configured!" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================"
Write-Host "Current Firewall Rules:"
Write-Host "========================================"

Get-NetFirewallRule -DisplayName "AIV-*" | Format-Table DisplayName, Enabled, Direction, Action -AutoSize

Write-Host ""
Write-Host "Tips:" -ForegroundColor Yellow
Write-Host "  - Port 8010: Video HTTP Server" -ForegroundColor Gray
Write-Host "  - Port 8502: Streamlit Web UI" -ForegroundColor Gray
Write-Host "  - LAN access only (Private/Domain network)" -ForegroundColor Gray
Write-Host ""

