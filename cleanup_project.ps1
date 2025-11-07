# ==================================================================================
# 项目清理脚本 - 准备GitHub备份
# ==================================================================================

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  项目清理脚本 - 准备GitHub备份" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Continue"

# 确保在项目根目录
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# ==================================================================================
# 步骤1: 创建目录
# ==================================================================================
Write-Host "[1/5] 创建新目录结构..." -ForegroundColor Yellow

$directories = @("tools", "docs")
foreach ($dir in $directories) {
    $path = Join-Path $projectRoot $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  [+] 创建目录: $dir" -ForegroundColor Green
    } else {
        Write-Host "  [✓] 目录已存在: $dir" -ForegroundColor Gray
    }
}

# ==================================================================================
# 步骤2: 移动文件到新目录
# ==================================================================================
Write-Host "`n[2/5] 移动文件到新目录..." -ForegroundColor Yellow

# 移动到 tools/
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
        Write-Host "  [→] 移动: $file → tools/" -ForegroundColor Green
    } else {
        Write-Host "  [×] 文件不存在: $file" -ForegroundColor Gray
    }
}

# 移动到 docs/
$moveToDocs = @(
    "快速启动.txt",
    "QUICK_START.txt"
)

foreach ($file in $moveToDocs) {
    $srcPath = Join-Path $projectRoot $file
    $dstPath = Join-Path $projectRoot "docs\$file"
    if (Test-Path $srcPath) {
        Move-Item -Path $srcPath -Destination $dstPath -Force
        Write-Host "  [→] 移动: $file → docs/" -ForegroundColor Green
    } else {
        Write-Host "  [×] 文件不存在: $file" -ForegroundColor Gray
    }
}

# ==================================================================================
# 步骤3: 删除不需要的文件
# ==================================================================================
Write-Host "`n[3/5] 删除不需要的文件..." -ForegroundColor Yellow

# 根目录删除列表
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
    "test_monitor.ps1",
    "查询视频评分状态.py"
)

foreach ($file in $deleteFromRoot) {
    $filePath = Join-Path $projectRoot $file
    if (Test-Path $filePath) {
        Remove-Item -Path $filePath -Force
        Write-Host "  [×] 删除: $file" -ForegroundColor Red
    } else {
        Write-Host "  [✓] 已不存在: $file" -ForegroundColor Gray
    }
}

# scripts/ 目录删除列表
$deleteFromScripts = @(
    "fix_ratings_constraint.py",
    "fix_trigger_logic.py",
    "migrate_add_model_sample.py",
    "recover_failed_fix.py",
    "refresh_order_json.py",
    "simple_monitor.py",
    "update_links.py"
)

foreach ($file in $deleteFromScripts) {
    $filePath = Join-Path $projectRoot "scripts\$file"
    if (Test-Path $filePath) {
        Remove-Item -Path $filePath -Force
        Write-Host "  [×] 删除: scripts\$file" -ForegroundColor Red
    } else {
        Write-Host "  [✓] 已不存在: scripts\$file" -ForegroundColor Gray
    }
}

# ==================================================================================
# 步骤4: 清理缓存目录
# ==================================================================================
Write-Host "`n[4/5] 清理缓存目录..." -ForegroundColor Yellow

$cacheDirs = @(
    "app\__pycache__",
    "scripts\__pycache__"
)

foreach ($dir in $cacheDirs) {
    $dirPath = Join-Path $projectRoot $dir
    if (Test-Path $dirPath) {
        Remove-Item -Path $dirPath -Recurse -Force
        Write-Host "  [×] 删除缓存: $dir" -ForegroundColor Red
    } else {
        Write-Host "  [✓] 缓存已清理: $dir" -ForegroundColor Gray
    }
}

# ==================================================================================
# 步骤5: 创建 .gitkeep 文件
# ==================================================================================
Write-Host "`n[5/5] 创建 .gitkeep 文件..." -ForegroundColor Yellow

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
            Write-Host "  [+] 创建: $dir\.gitkeep" -ForegroundColor Green
        } else {
            Write-Host "  [✓] 已存在: $dir\.gitkeep" -ForegroundColor Gray
        }
    }
}

# ==================================================================================
# 完成
# ==================================================================================
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "  清理完成！" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步：" -ForegroundColor Yellow
Write-Host "  1. 检查 .gitignore 文件（已自动创建）" -ForegroundColor White
Write-Host "  2. 检查 README.md 文件（已自动创建）" -ForegroundColor White
Write-Host "  3. 检查 requirements.txt 文件（已自动创建）" -ForegroundColor White
Write-Host "  4. 测试启动：.\lan_start_with_monitor.ps1" -ForegroundColor White
Write-Host "  5. 初始化Git仓库：git init" -ForegroundColor White
Write-Host "  6. 添加文件：git add ." -ForegroundColor White
Write-Host "  7. 提交：git commit -m 'Initial commit'" -ForegroundColor White
Write-Host ""
Write-Host "项目结构已整理完毕，可以备份到GitHub！" -ForegroundColor Green
Write-Host ""

