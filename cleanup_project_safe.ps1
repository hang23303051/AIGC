# ==================================================================================
# Project Cleanup Script - Prepare for GitHub Backup
# ==================================================================================

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Project Cleanup Script - Prepare for GitHub Backup" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Continue"

# Ensure we're in the project root
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ==================================================================================
# Step 1: Create directories
# ==================================================================================
Write-Host "[1/5] Creating directory structure..." -ForegroundColor Yellow

$directories = @("tools", "docs")
foreach ($dir in $directories) {
    $path = Join-Path $projectRoot $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  [+] Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "  [v] Exists: $dir" -ForegroundColor Gray
    }
}

# ==================================================================================
# Step 2: Move files to new directories
# ==================================================================================
Write-Host "`n[2/5] Moving files to new directories..." -ForegroundColor Yellow

# Move to tools/
$moveToTools = @(
    "restore_from_backup.py",
    "restore_and_migrate.py",
    "verify_backup.py",
    "lan_status.ps1"
)

foreach ($file in $moveToTools) {
    $srcPath = Join-Path $projectRoot $file
    $dstPath = Join-Path $projectRoot "tools\$file"
    if (Test-Path $srcPath) {
        Move-Item -Path $srcPath -Destination $dstPath -Force
        Write-Host "  [>] Moved: $file -> tools/" -ForegroundColor Green
    } else {
        Write-Host "  [x] Not found: $file" -ForegroundColor Gray
    }
}

# Move to docs/ (handle Chinese filename)
Write-Host "  [*] Moving documentation files..." -ForegroundColor Yellow
$quickStartFiles = Get-ChildItem -Path $projectRoot -Filter "*.txt" | Where-Object { 
    $_.Name -like "*启动*" -or $_.Name -like "QUICK_START*" 
}

foreach ($file in $quickStartFiles) {
    $dstPath = Join-Path $projectRoot "docs\$($file.Name)"
    if (Test-Path $file.FullName) {
        Move-Item -Path $file.FullName -Destination $dstPath -Force
        Write-Host "  [>] Moved: $($file.Name) -> docs/" -ForegroundColor Green
    }
}

# ==================================================================================
# Step 3: Delete unnecessary files
# ==================================================================================
Write-Host "`n[3/5] Deleting unnecessary files..." -ForegroundColor Yellow

# Delete from root directory
$deleteFromRoot = @(
    "check_db_detailed.py",
    "check_missing_samples.py",
    "check_unsubmitted.py",
    "check_wan21_paths.py",
    "fix_autosave.ps1",
    "fix_ratings_table.py",
    "lan_start.ps1",
    "reorganize_wan21_videos.ps1",
    "setup_firewall_admin.ps1",
    "start_monitor.ps1",
    "sync_all_videos_complete.ps1",
    "sync_wan21_videos.ps1",
    "test_monitor.ps1"
)

# Handle Chinese filename separately
$chineseQueryFile = Get-ChildItem -Path $projectRoot -Filter "*.py" | Where-Object { 
    $_.Name -like "*查询*" -or $_.Name -like "*状态*"
}
if ($chineseQueryFile) {
    $deleteFromRoot += $chineseQueryFile.Name
}

foreach ($file in $deleteFromRoot) {
    $filePath = Join-Path $projectRoot $file
    if (Test-Path $filePath) {
        Remove-Item -Path $filePath -Force
        Write-Host "  [x] Deleted: $file" -ForegroundColor Red
    } else {
        Write-Host "  [v] Not exists: $file" -ForegroundColor Gray
    }
}

# Delete from scripts/ directory
$deleteFromScripts = @(
    "fix_ratings_constraint.py",
    "fix_trigger_logic.py",
    "migrate_add_model_sample.py",
    "recover_failed_fix.py",
    "refresh_order_json.py",
    "update_links.py"
)

foreach ($file in $deleteFromScripts) {
    $filePath = Join-Path $projectRoot "scripts\$file"
    if (Test-Path $filePath) {
        Remove-Item -Path $filePath -Force
        Write-Host "  [x] Deleted: scripts\$file" -ForegroundColor Red
    } else {
        Write-Host "  [v] Not exists: scripts\$file" -ForegroundColor Gray
    }
}

# ==================================================================================
# Step 4: Clean cache directories
# ==================================================================================
Write-Host "`n[4/5] Cleaning cache directories..." -ForegroundColor Yellow

$cacheDirs = @(
    "app\__pycache__",
    "scripts\__pycache__"
)

foreach ($dir in $cacheDirs) {
    $dirPath = Join-Path $projectRoot $dir
    if (Test-Path $dirPath) {
        Remove-Item -Path $dirPath -Recurse -Force
        Write-Host "  [x] Deleted cache: $dir" -ForegroundColor Red
    } else {
        Write-Host "  [v] Cache cleaned: $dir" -ForegroundColor Gray
    }
}

# ==================================================================================
# Step 5: Create .gitkeep files
# ==================================================================================
Write-Host "`n[5/5] Creating .gitkeep files..." -ForegroundColor Yellow

$gitkeepDirs = @(
    "backup",
    "export_results",
    "video"
)

foreach ($dir in $gitkeepDirs) {
    $dirPath = Join-Path $projectRoot $dir
    $gitkeepPath = Join-Path $dirPath ".gitkeep"
    if (Test-Path $dirPath) {
        if (-not (Test-Path $gitkeepPath)) {
            New-Item -ItemType File -Path $gitkeepPath -Force | Out-Null
            Write-Host "  [+] Created: $dir\.gitkeep" -ForegroundColor Green
        } else {
            Write-Host "  [v] Exists: $dir\.gitkeep" -ForegroundColor Gray
        }
    }
}

# ==================================================================================
# Complete
# ==================================================================================
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  Cleanup Complete!" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check .gitignore file (auto-created)" -ForegroundColor White
Write-Host "  2. Check README.md file (auto-created)" -ForegroundColor White
Write-Host "  3. Check requirements.txt file (auto-created)" -ForegroundColor White
Write-Host "  4. Test startup: .\lan_start_with_monitor.ps1" -ForegroundColor White
Write-Host "  5. Initialize Git: git init" -ForegroundColor White
Write-Host "  6. Add files: git add ." -ForegroundColor White
Write-Host "  7. Commit: git commit -m 'Initial commit'" -ForegroundColor White
Write-Host ""
Write-Host "Project is ready for GitHub backup!" -ForegroundColor Green
Write-Host ""

# Display summary
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Summary:" -ForegroundColor Yellow
Write-Host "  - Created 2 directories (tools/, docs/)" -ForegroundColor White
Write-Host "  - Moved 6 files to new locations" -ForegroundColor White
Write-Host "  - Deleted ~21 unnecessary files" -ForegroundColor White
Write-Host "  - Cleaned __pycache__ directories" -ForegroundColor White
Write-Host "  - Created .gitkeep files for empty dirs" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

