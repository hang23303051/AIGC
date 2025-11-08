# Compare Mode - Firewall Configuration
# Requires Administrator privileges

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] Please run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then:" -ForegroundColor Yellow
    Write-Host "  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass" -ForegroundColor White
    Write-Host "  cd D:\code\github\AIGC" -ForegroundColor White
    Write-Host "  .\scripts\setup_firewall_compare.ps1" -ForegroundColor White
    Write-Host ""
    exit
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Compare Mode - Firewall Configuration" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Remove old rules
Write-Host "Removing old rules..." -ForegroundColor Yellow
Remove-NetFirewallRule -DisplayName "AIV Compare - Streamlit UI (8503)" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "AIV Compare - Video Server (8011)" -ErrorAction SilentlyContinue

# Add new rule - Streamlit UI (8503)
Write-Host "Adding rule: Streamlit UI (port 8503)..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "AIV Compare - Streamlit UI (8503)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8503 `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Compare Mode - Streamlit UI" `
    | Out-Null

Write-Host "  [OK] Port 8503 opened" -ForegroundColor Green

# Add new rule - Video Server (8011)
Write-Host "Adding rule: Video Server (port 8011)..." -ForegroundColor Cyan
New-NetFirewallRule -DisplayName "AIV Compare - Video Server (8011)" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8011 `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Compare Mode - Video Server" `
    | Out-Null

Write-Host "  [OK] Port 8011 opened" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Firewall Configuration Completed!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opened ports:" -ForegroundColor Yellow
Write-Host "  8503 - Streamlit UI" -ForegroundColor White
Write-Host "  8011 - Video Server" -ForegroundColor White
Write-Host ""

