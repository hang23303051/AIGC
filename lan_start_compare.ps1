# Compare Mode - Start Services
# Streamlit UI (8503) + Video Server (8011) + Monitor Service

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Compare Mode - Starting Services" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# Check database
if (-not (Test-Path "aiv_compare_v1.db")) {
    Write-Host ""
    Write-Host "[ERROR] Database not found! Please initialize first:" -ForegroundColor Red
    Write-Host "  1. python scripts\prepare_data_compare.py" -ForegroundColor Yellow
    Write-Host "  2. python scripts\setup_project_compare.py --judges 10" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit
}

# Get local IP (skip loopback, virtual adapters, and APIPA addresses)
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notlike "*Loopback*" -and 
    $_.InterfaceAlias -notlike "*VirtualBox*" -and 
    $_.InterfaceAlias -notlike "*VMware*" -and
    $_.IPAddress -notlike "169.254.*" -and
    $_.PrefixOrigin -eq "Dhcp" -or $_.PrefixOrigin -eq "Manual"
} | Select-Object -First 1).IPAddress

if (-not $localIP) {
    # Fallback: try to get any valid IP (not 169.254.x.x)
    $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike "127.*" -and 
        $_.IPAddress -notlike "169.254.*"
    } | Select-Object -First 1).IPAddress
}

if (-not $localIP) {
    $localIP = "localhost"
}

Write-Host ""
Write-Host "Local IP: $localIP" -ForegroundColor Yellow
Write-Host ""

# 1. Start Video Server (Port 8011)
Write-Host "[1/3] Starting video server (port 8011)..." -ForegroundColor Cyan
$videoServerJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m http.server 8011 --bind 0.0.0.0 --directory .
}
Write-Host "  Video server started (Job ID: $($videoServerJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 2

# 2. Start Streamlit UI (Port 8503)
Write-Host ""
Write-Host "[2/3] Starting Streamlit UI (port 8503)..." -ForegroundColor Cyan
$uiJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    streamlit run app\streamlit_app_compare.py --server.port 8503 --server.address 0.0.0.0 --server.headless true
}
Write-Host "  Streamlit UI started (Job ID: $($uiJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 3

# 3. Start Monitor Service
Write-Host ""
Write-Host "[3/3] Starting monitor service (every 300 seconds)..." -ForegroundColor Cyan
$monitorJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python scripts\monitor_new_videos_compare.py --interval 300
}
Write-Host "  Monitor service started (Job ID: $($monitorJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 2

# Display access info
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Services Started Successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# Save job info
$jobInfo = @{
    VideoServer = $videoServerJob.Id
    UI = $uiJob.Id
    Monitor = $monitorJob.Id
}
$jobInfo | ConvertTo-Json | Out-File -FilePath ".compare_jobs.json" -Encoding UTF8

# Get judge links
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Judge Access Links" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Local IP: $localIP" -ForegroundColor White
Write-Host "UI Port: 8503" -ForegroundColor White
Write-Host ""

# Use Python to get judge links
$pythonOutput = python -c @"
import sqlite3
conn = sqlite3.connect('aiv_compare_v1.db')
cursor = conn.cursor()
cursor.execute('SELECT judge_name, uid FROM judges ORDER BY judge_name')
for row in cursor.fetchall():
    print(f'{row[0]}|{row[1]}')
conn.close()
"@

foreach ($line in $pythonOutput) {
    $parts = $line -split '\|'
    if ($parts.Length -eq 2) {
        $judgeName = $parts[0]
        $uid = $parts[1]
        Write-Host "[$judgeName]" -ForegroundColor Cyan
        Write-Host "  http://${localIP}:8503/?uid=$uid" -ForegroundColor White
        Write-Host ""
    }
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop services: .\lan_stop_compare.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "Services are running in background. You can close this window." -ForegroundColor Gray
Write-Host ""

