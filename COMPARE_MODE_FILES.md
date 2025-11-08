# 比较评测模式 - 新增文件清单

本文档列出了为实现比较评测模式新增的所有文件。

## 📁 新增文件列表

### 核心脚本

#### 数据库相关

- **`db/schema_compare.sql`**
  - 比较模式的数据库结构定义
  - 包含6个核心表：judges, prompts, videos, tasks, assignments, comparisons
  - 包含2个触发器：自动更新任务状态、自动清理完成任务

#### 数据准备与初始化

- **`scripts/prepare_data_compare.py`**
  - 扫描video2目录下的生成视频
  - 扫描video/refvideo目录下的参考视频
  - 生成两两配对的比较任务清单
  - 输出到data/comparison_tasks.csv

- **`scripts/setup_project_compare.py`**
  - 创建比较模式数据库（aiv_compare_v1.db）
  - 创建评审员账户
  - 导入参考视频和生成视频
  - 创建比较任务
  - 随机分配任务给评审员

#### UI应用

- **`app/streamlit_app_compare.py`**
  - Streamlit比较评测UI
  - 左侧显示参考视频
  - 右侧上下叠放两个生成视频
  - 提供选择按钮（选A、选B、两者相当）
  - 显示进度和任务信息

#### 监控服务

- **`scripts/monitor_new_videos_compare.py`**
  - 自动监控video2目录
  - 检测新增视频并创建比较任务
  - 检测删除视频并清理未完成任务
  - 支持动态添加新模型
  - 可选参数：--once（立即扫描一次）、--interval（监控间隔）

#### 数据导出

- **`scripts/export_ratings_compare.py`**
  - 导出比较评测结果
  - 支持多种格式：
    - comparisons_long_*.csv（详细评测记录）
    - task_summary_*.csv（任务汇总）
    - model_stats_*.csv（模型统计）
    - summary_*.txt（进度摘要）

#### 防火墙配置

- **`scripts/setup_firewall_compare.ps1`**
  - Windows防火墙配置脚本
  - 开放端口8503（UI）
  - 开放端口8011（视频服务）
  - 需要管理员权限运行

### 启动与管理脚本

- **`lan_start_compare.ps1`**
  - 一键启动比较模式所有服务
  - 启动Streamlit UI（端口8503）
  - 启动视频服务器（端口8011）
  - 启动监控服务（每5分钟扫描）
  - 显示本机IP和访问地址

- **`lan_stop_compare.ps1`**
  - 停止比较模式所有服务
  - 清理后台Job
  - 强制停止占用端口的进程

- **`export_all_compare.ps1`**
  - 一键导出所有评测数据
  - 调用export_ratings_compare.py

### 辅助工具

- **`check_progress_compare.py`**
  - 查看评测进度
  - 显示任务完成情况
  - 显示评审员进度
  - 显示模型比较统计
  - 显示类别进度

- **`get_links_compare.py`**
  - 获取所有评审员的访问链接
  - 显示本机IP和局域网IP
  - 包含完整的带UID的URL

### 文档

- **`README_COMPARE.md`**
  - 比较模式的完整文档
  - 包含快速开始指南
  - 包含系统架构说明
  - 包含故障排除指南
  - 包含数据导出格式说明

- **`docs/快速启动_比较模式.txt`**
  - 中文快速启动指南
  - 包含所有常用命令
  - 包含常见问题解答

- **`COMPARE_MODE_FILES.md`**
  - 本文件，新增文件清单

### 更新的文件

- **`README.md`**
  - 添加了比较模式的说明章节
  - 添加了双模式对比表格
  - 添加了比较模式文档链接

## 📊 文件统计

### 按类型分类

| 类型 | 数量 | 文件 |
|------|-----|------|
| Python脚本 | 6 | prepare_data_compare.py, setup_project_compare.py, streamlit_app_compare.py, monitor_new_videos_compare.py, export_ratings_compare.py, check_progress_compare.py, get_links_compare.py |
| PowerShell脚本 | 4 | lan_start_compare.ps1, lan_stop_compare.ps1, export_all_compare.ps1, setup_firewall_compare.ps1 |
| SQL文件 | 1 | schema_compare.sql |
| Markdown文档 | 2 | README_COMPARE.md, COMPARE_MODE_FILES.md |
| 文本文档 | 1 | 快速启动_比较模式.txt |
| **总计** | **14** | |

### 按功能分类

| 功能 | 文件数 | 说明 |
|------|--------|------|
| 核心业务逻辑 | 5 | 数据准备、初始化、UI、监控、导出 |
| 启动管理 | 4 | 启动、停止、防火墙、导出 |
| 辅助工具 | 2 | 进度查看、链接获取 |
| 文档 | 3 | 完整文档、快速指南、文件清单 |

## 🔧 配置信息

### 端口配置

| 服务 | 端口 |
|------|------|
| Streamlit UI | 8503 |
| 视频服务器 | 8011 |

### 目录配置

| 用途 | 路径 |
|------|------|
| 参考视频 | `D:\code\github\AIGC\video\refvideo` |
| 生成视频 | `D:\code\github\AIGC\video2` |
| Prompt文本 | `D:\code\github\AIGC\prompt` |
| 数据库 | `D:\code\github\AIGC\aiv_compare_v1.db` |
| 任务清单 | `D:\code\github\AIGC\data\comparison_tasks.csv` |
| 导出结果 | `D:\code\github\AIGC\export_results_compare` |

### 数据库表

| 表名 | 说明 |
|------|------|
| judges | 评审员信息 |
| prompts | 参考视频信息 |
| videos | 生成视频信息 |
| tasks | 比较任务（model_a vs model_b） |
| assignments | 任务分配（评审员×任务） |
| comparisons | 比较结果（评审员的选择） |

## 🚀 使用流程

### 首次部署

```powershell
# 1. 准备数据
python scripts\prepare_data_compare.py

# 2. 初始化数据库
python scripts\setup_project_compare.py --judges 10

# 3. 配置防火墙（可选）
.\scripts\setup_firewall_compare.ps1

# 4. 启动服务
.\lan_start_compare.ps1

# 5. 获取评审员链接
python get_links_compare.py
```

### 日常使用

```powershell
# 启动
.\lan_start_compare.ps1

# 查看进度
python check_progress_compare.py

# 导出数据
.\export_all_compare.ps1

# 停止
.\lan_stop_compare.ps1
```

## 📝 与原系统的隔离

比较模式与打分模式（原系统）完全独立：

| 隔离项 | 打分模式 | 比较模式 |
|--------|---------|---------|
| 数据库文件 | aiv_eval_v4.db | aiv_compare_v1.db |
| UI端口 | 8502 | 8503 |
| 视频服务端口 | 8010 | 8011 |
| 生成视频目录 | video/genvideo/ | video2/ |
| 导出目录 | export_results/ | export_results_compare/ |
| 启动脚本 | lan_start_with_monitor.ps1 | lan_start_compare.ps1 |
| 停止脚本 | lan_stop.ps1 | lan_stop_compare.ps1 |

**两个系统可以同时运行**，互不干扰！

## ✨ 核心特性

1. **两两配对比较**
   - N个模型生成C(N,2)个比较任务
   - 避免主观打分偏见

2. **三人评测制**
   - 每个任务需3个不同评审员
   - 达到3次后自动完成

3. **动态监控**
   - 自动检测新增视频
   - 自动创建比较任务
   - 支持运行时添加新模型

4. **独立运行**
   - 与打分模式完全隔离
   - 可同时运行两个系统

5. **简化评测**
   - 只需选择更好的一个
   - 无需量化打分

## 🎯 任务生成逻辑

对于每个参考视频：
- 如果有2个生成视频 → 生成1个任务（A vs B）
- 如果有3个生成视频 → 生成3个任务（A vs B, A vs C, B vs C）
- 如果有4个生成视频 → 生成6个任务
- 如果有N个生成视频 → 生成C(N,2) = N×(N-1)/2个任务

## 📦 依赖项

比较模式使用与打分模式相同的依赖：

```
streamlit>=1.28.0
pandas>=2.0.0
```

无需额外安装依赖。

## 🔍 数据导出格式

### comparisons_long_*.csv
每行一个评测记录，包含：
- 任务信息（sample_id, model_a, model_b）
- 评审员信息（judge_id, judge_name）
- 选择结果（chosen_model）
- 评论和时间

### task_summary_*.csv
每行一个任务，包含：
- 任务基本信息
- 完成状态
- 所有评审员的选择
- 统计（model_a_wins, model_b_wins, ties）

### model_stats_*.csv
每行一个模型，包含：
- 模型名称
- 胜出次数
- 参与任务数
- 胜率

## 💡 设计亮点

1. **完全独立**：与原系统零耦合，可安全部署
2. **易于扩展**：支持动态添加模型，无需修改代码
3. **自动化**：监控、任务创建、状态更新全自动
4. **容错性**：触发器保证数据一致性
5. **灵活性**：可选手动或自动监控
6. **友好性**：详细的文档和命令行提示

## 📞 技术支持

如有问题，请参考：
1. [README_COMPARE.md](README_COMPARE.md) - 完整文档
2. [docs/快速启动_比较模式.txt](docs/快速启动_比较模式.txt) - 快速指南
3. GitHub Issues - 提交问题

---

**所有文件均已创建完成，系统可以立即投入使用！**

