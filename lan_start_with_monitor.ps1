# AI Video Evaluation System - Startup Script with Monitor
# 带视频监控的启动脚本

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

# Python interpreter path
$pythonExe = "D:\miniconda3\envs\learn\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI Video Evaluation System" -ForegroundColor Cyan
Write-Host "  with Video Monitor" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# Get local IP
function Get-LocalIP {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.254.*"}).IPAddress | Select-Object -First 1
        if (-not $ip) { $ip = "127.0.0.1" }
        return $ip
    } catch {
        return "127.0.0.1"
    }
}
$localIP = Get-LocalIP
Write-Host "`n[INFO] Local IP: $localIP" -ForegroundColor Green
Write-Host "[INFO] Samples: 1000+, Models: 5+" -ForegroundColor Yellow
Write-Host "[INFO] Auto-update: ENABLED" -ForegroundColor Green
Write-Host "[INFO] Project Root: $projectRoot" -ForegroundColor Gray

# Check firewall
Write-Host "`n[1/7] Checking firewall..." -ForegroundColor Yellow
$firewallRules = Get-NetFirewallRule -DisplayName "*AIV-VideoService-8010*", "*AIV-WebUI-8502*" -ErrorAction SilentlyContinue
if ($firewallRules.Count -eq 2 -and ($firewallRules | Where-Object {$_.Enabled -eq $true}).Count -eq 2) {
    Write-Host "  [OK] Firewall configured" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Firewall not configured" -ForegroundColor Yellow
    Write-Host "  Run as admin: .\scripts\setup_firewall.ps1" -ForegroundColor Cyan
}

# Check Python and dependencies
Write-Host "`n[2/7] Checking Python environment..." -ForegroundColor Yellow
if (Test-Path $pythonExe) {
    Write-Host "  [OK] Python: $pythonExe" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Python not found at: $pythonExe" -ForegroundColor Red
    Write-Host "  Please update the pythonExe variable in this script" -ForegroundColor Yellow
    pause
    exit 1
}

# Check database
Write-Host "`n[3/7] Checking database..." -ForegroundColor Yellow
$dbPath = Join-Path $projectRoot "aiv_eval_v4.db"
if (Test-Path $dbPath) {
    Write-Host "  [OK] Database exists: aiv_eval_v4.db" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Database not found" -ForegroundColor Red
    Write-Host "  Run: & '$pythonExe' scripts\prepare_data.py" -ForegroundColor White
    Write-Host "  Then: & '$pythonExe' scripts\setup_project.py --db aiv_eval_v4.db --csv data\prompts.csv --judges 10" -ForegroundColor White
    pause
    exit 1
}

# Start video service
Write-Host "`n[4/7] Starting video service (port 8010)..." -ForegroundColor Yellow
$videoPath = Join-Path $projectRoot "video\human_eval_v4"
if (-not (Test-Path $videoPath)) {
    Write-Host "  [ERROR] Video directory not found: $videoPath" -ForegroundColor Red
    Write-Host "  Please run prepare_data.py first" -ForegroundColor Yellow
    pause
    exit 1
}

Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "cd '$videoPath'; Write-Host '[Video Service - Port 8010]' -ForegroundColor Green; Write-Host 'URL: http://${localIP}:8010' -ForegroundColor Cyan; & '$pythonExe' -m http.server 8010"

Start-Sleep -Seconds 2
Write-Host "  [OK] Video service started" -ForegroundColor Green

# Start web UI
Write-Host "`n[5/7] Starting web UI (port 8502)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "cd '$projectRoot'; Write-Host '[Web UI - Port 8502]' -ForegroundColor Green; Write-Host 'URL: http://${localIP}:8502' -ForegroundColor Cyan; `$env:AIV_DB='aiv_eval_v4.db'; `$env:AIV_DATA_SCALE='large'; & '$pythonExe' -m streamlit run app\streamlit_app.py --server.port 8502 --server.address 0.0.0.0"

Start-Sleep -Seconds 2
Write-Host "  [OK] Web UI started" -ForegroundColor Green

# Start monitor service
Write-Host "`n[6/7] Starting video monitor service..." -ForegroundColor Yellow
$monitorInterval = 300  # 5 minutes
Write-Host "  Scan interval: $monitorInterval seconds (5 minutes)" -ForegroundColor Gray
Write-Host "  Monitor window will show scan timestamps" -ForegroundColor Cyan
Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "cd '$projectRoot'; `$Host.UI.RawUI.WindowTitle='Video Monitor - Every $monitorInterval sec'; Write-Host '========================================' -ForegroundColor Cyan; Write-Host '  Video Monitor Service' -ForegroundColor Green; Write-Host '  Scan Interval: $monitorInterval seconds (5 minutes)' -ForegroundColor Yellow; Write-Host '========================================' -ForegroundColor Cyan; Write-Host ''; Write-Host 'This window will display:' -ForegroundColor White; Write-Host '  - Scan start/end timestamps' -ForegroundColor Gray; Write-Host '  - Detected new videos' -ForegroundColor Gray; Write-Host '  - Task updates' -ForegroundColor Gray; Write-Host ''; Write-Host 'Keep this window open!' -ForegroundColor Yellow; Write-Host ''; Write-Host 'Starting monitor service...' -ForegroundColor Cyan; Write-Host ''; & '$pythonExe' -u scripts\simple_monitor.py --interval $monitorInterval"

Start-Sleep -Seconds 2
Write-Host "  [OK] Monitor service started" -ForegroundColor Green

# Wait for services
Write-Host "`n[7/7] Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# Display access info
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Services Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nData Configuration:" -ForegroundColor Yellow
Write-Host "  Samples: 1000+" -ForegroundColor White
Write-Host "  Models: 5+ (auto-expanding)" -ForegroundColor White
Write-Host "  Database: aiv_eval_v4.db" -ForegroundColor White
Write-Host "  Auto-update: Every $monitorInterval seconds" -ForegroundColor Green

Write-Host "`nLocal Access:" -ForegroundColor Yellow
Write-Host "  Web UI: http://localhost:8502" -ForegroundColor Green
Write-Host "  Video:  http://localhost:8010" -ForegroundColor Green

# Get and display reviewer links
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Reviewer Access Links" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

try {
    Write-Host ""
    & $pythonExe get_links.py
    Write-Host ""
} catch {
    Write-Host "`n[WARN] Could not retrieve reviewer links" -ForegroundColor Yellow
    Write-Host "Run manually: & '$pythonExe' get_links.py" -ForegroundColor White
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "`nRunning Services (3 separate windows):" -ForegroundColor Yellow
Write-Host "  1. Video Service (port 8010)" -ForegroundColor White
Write-Host "  2. Web UI (port 8502)" -ForegroundColor White
Write-Host "  3. Video Monitor (auto-update every $monitorInterval sec)" -ForegroundColor Green
Write-Host "     └─ Shows scan timestamps and detected changes" -ForegroundColor Gray

Write-Host "`nMonitor Window:" -ForegroundColor Yellow
Write-Host "  - Window title: 'Video Monitor - Every $monitorInterval sec'" -ForegroundColor Cyan
Write-Host "  - Displays: [YYYY-MM-DD HH:MM:SS] scan start/end times" -ForegroundColor Cyan
Write-Host "  - First scan starts immediately" -ForegroundColor Gray

Write-Host "`nStop all services:" -ForegroundColor Yellow
Write-Host "  .\lan_stop.ps1" -ForegroundColor White

Write-Host "`nPython: $pythonExe" -ForegroundColor Gray
Write-Host "`nKeep this window and the THREE service windows open!" -ForegroundColor Cyan
Write-Host "New videos will be automatically detected and added to tasks!" -ForegroundColor Green
Write-Host ""

