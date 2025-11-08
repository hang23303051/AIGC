# Compare Mode - Stop Services
# Stop all compare mode related services

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Compare Mode - Stopping Services" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Read job info
if (Test-Path ".compare_jobs.json") {
    $jobInfo = Get-Content ".compare_jobs.json" | ConvertFrom-Json
    
    Write-Host "Stopping background jobs..." -ForegroundColor Yellow
    
    # Stop jobs
    if ($jobInfo.VideoServer) {
        Stop-Job -Id $jobInfo.VideoServer -ErrorAction SilentlyContinue
        Remove-Job -Id $jobInfo.VideoServer -ErrorAction SilentlyContinue
        Write-Host "  Video server stopped" -ForegroundColor Green
    }
    
    if ($jobInfo.UI) {
        Stop-Job -Id $jobInfo.UI -ErrorAction SilentlyContinue
        Remove-Job -Id $jobInfo.UI -ErrorAction SilentlyContinue
        Write-Host "  Streamlit UI stopped" -ForegroundColor Green
    }
    
    if ($jobInfo.Monitor) {
        Stop-Job -Id $jobInfo.Monitor -ErrorAction SilentlyContinue
        Remove-Job -Id $jobInfo.Monitor -ErrorAction SilentlyContinue
        Write-Host "  Monitor service stopped" -ForegroundColor Green
    }
    
    Remove-Item ".compare_jobs.json" -ErrorAction SilentlyContinue
}

# Force stop processes on ports
Write-Host ""
Write-Host "Checking port usage..." -ForegroundColor Yellow

# Port 8503 (Streamlit UI)
$port8503 = Get-NetTCPConnection -LocalPort 8503 -ErrorAction SilentlyContinue
if ($port8503) {
    $pid = $port8503.OwningProcess
    Write-Host "  Stopping process on port 8503 (PID: $pid)" -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

# Port 8011 (Video Server)
$port8011 = Get-NetTCPConnection -LocalPort 8011 -ErrorAction SilentlyContinue
if ($port8011) {
    $pid = $port8011.OwningProcess
    Write-Host "  Stopping process on port 8011 (PID: $pid)" -ForegroundColor Yellow
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

# Stop streamlit processes (compare mode)
$streamlitProcesses = Get-Process | Where-Object {$_.CommandLine -like "*streamlit_app_compare.py*"} -ErrorAction SilentlyContinue
if ($streamlitProcesses) {
    $streamlitProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Streamlit processes stopped" -ForegroundColor Green
}

# Stop monitor processes (compare mode)
$monitorProcesses = Get-Process | Where-Object {$_.CommandLine -like "*monitor_new_videos_compare.py*"} -ErrorAction SilentlyContinue
if ($monitorProcesses) {
    $monitorProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Monitor processes stopped" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " All Services Stopped" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

