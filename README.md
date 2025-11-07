# AI视频生成效果评测系统 (AIV MOS v4)

<div align="center">

**一个基于局域网的AI视频生成模型人工评测系统**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[快速开始](#快速开始) • [系统架构](#系统架构) • [功能特性](#功能特性) • [文档](#文档)

</div>

---

## 📋 项目简介

本项目是一个用于视频生成模型人工评测的系统，支持局域网访问，特别适用于校园网等内网环境。采用**三人评测制**，每个任务需3个不同评审员评测后自动完成并从任务池中移除，大幅降低评测工作量。

### 🎯 核心特性

- **三人评测制**：每个视频对只需3个评审员评测，评满即完成
- **共享任务池**：所有评审员共享任务池，工作量自动平衡
- **动态监控**：自动监控新增视频，自动创建评测任务
- **四维度评分**：基本语义对齐、运动、事件时序一致性、真实度
- **盲评机制**：默认隐藏模型名称，避免评分偏见
- **局域网部署**：无需公网，安全可靠

### 📊 数据规模

- **参考视频**：1098个（9个类别）
- **生成视频**：~3000+个（5个模型）
- **评测任务**：~2200+个视频对
- **评审员**：10人
- **评测次数**：每个任务3次，总计~6600次评分

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.9+
- **操作系统**: Windows 10/11 (推荐)
- **网络**: 局域网环境
- **磁盘空间**: ~50GB (包含视频文件)

### 安装依赖

```powershell
# 安装Python依赖
pip install -r requirements.txt
```

### 首次部署

#### 1️⃣ 准备数据

```powershell
python scripts\prepare_data.py
```

**功能**：扫描视频文件，生成评测任务清单

#### 2️⃣ 初始化数据库

```powershell
python scripts\setup_project.py --db aiv_eval_v4.db --csv data\prompts.csv --judges 10
```

**功能**：创建数据库、评审员账户、任务分配

#### 3️⃣ 配置防火墙（管理员权限）

```powershell
# 以管理员身份运行PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_firewall.ps1
```

**功能**：允许端口8502（UI）和8010（视频服务）

#### 4️⃣ 启动服务

```powershell
.\lan_start_with_monitor.ps1
```

**功能**：启动Streamlit UI + 视频服务器 + 监控服务

#### 5️⃣ 获取评审员链接

```powershell
python get_links.py
```

**输出示例**：
```
评审员1: http://172.16.82.12:8502/?uid=abc123
评审员2: http://172.16.82.12:8502/?uid=def456
...
```

将链接分发给评审员即可开始评测！

---

## 📁 项目结构

```
aiv_mos_v4/
├── app/
│   └── streamlit_app.py           # Streamlit UI主程序
├── db/
│   └── schema.sql                 # 数据库结构定义（SQLite）
├── scripts/                        # 核心脚本
│   ├── prepare_data.py            # 数据准备
│   ├── setup_project.py           # 项目初始化
│   ├── migrate_v1_to_v2.py        # 数据库迁移（V1→V2）
│   ├── monitor_new_videos.py      # 视频监控服务
│   ├── shuffle_pending_tasks.py   # 任务随机打散
│   ├── export_ratings.py          # 导出评分数据
│   ├── fix_prompt_text.py         # 修复Prompt文本
│   └── setup_firewall.ps1         # 防火墙配置
├── tools/                          # 辅助工具
│   ├── restore_from_backup.py     # 备份恢复
│   ├── verify_backup.py           # 备份验证
│   └── lan_status.ps1             # 服务状态检查
├── docs/                           # 文档
│   ├── 快速启动.txt                # 中文快速启动指南
│   └── QUICK_START.txt            # 英文快速启动指南
├── data/                           # 配置数据
│   ├── prompts.csv                # 评测任务清单
│   └── scoring_examples.json      # 评分示例
├── prompt/                         # Prompt文本文件
│   ├── animals_and_ecology/
│   ├── architecture/
│   ├── commercial_marketing/
│   ├── food/
│   ├── industrial_activity/
│   ├── landscape/
│   ├── people_daily/
│   ├── sports_competition/
│   └── transportation/
├── video/                          # 视频目录（不上传到Git）
│   ├── refvideo/                  # 参考视频（真实世界视频）
│   ├── genvideo/                  # 生成视频（AI模型生成）
│   └── human_eval_v4/             # 静态服务目录
├── backup/                         # 数据库备份（不上传）
├── export_results/                 # 导出结果（不上传）
├── lan_start_with_monitor.ps1     # 启动脚本（带监控）
├── lan_stop.ps1                   # 停止脚本
├── export_all.ps1                 # 一键导出数据
├── check_progress.py              # 查看评测进度
├── get_links.py                   # 获取评审员链接
├── check_db_version.py            # 检查数据库版本
├── query_video_status.py          # 查询视频评分状态
├── rule.txt                       # 详细评分规则
├── .gitignore                     # Git忽略配置
├── requirements.txt               # Python依赖
└── README.md                      # 本文件
```

---

## 🎯 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     局域网访问层                          │
│  10个评审员 × 独立token → http://<LocalIP>:8502/?uid=... │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Streamlit UI 服务                       │
│            (app/streamlit_app.py, Port 8502)            │
│  功能：任务分配、评分界面、进度跟踪、规则展示            │
└─────────────────────────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
┌─────────────────────┐  ┌──────────────────────────┐
│  SQLite数据库       │  │  Python HTTP视频服务器    │
│  (aiv_eval_v4.db)  │  │  (Port 8010)             │
│  存储：评分、任务   │  │  提供：参考视频+生成视频  │
└─────────────────────┘  └──────────────────────────┘
```

### 数据库设计（V2系统 - 三人评测制）

**核心表**：
- `judges` - 评审员信息
- `prompts` - 参考视频信息
- `videos` - 生成视频信息
- `tasks` - 评测任务（每个视频对一个任务）
- `assignments` - 任务分配（judge × task，随机顺序）
- `ratings` - 评分记录（4个维度）

**关键机制**：
1. 每个任务需要3个不同评审员评测
2. 评满3次后自动标记完成（触发器自动处理）
3. 完成的任务自动从所有人的列表中移除
4. 每个评审员看到的任务顺序不同（随机化）

---

## ⚙️ 日常操作

### 启动服务

```powershell
.\lan_start_with_monitor.ps1
```

**启动内容**：
- Streamlit UI（端口8502）
- 视频HTTP服务器（端口8010）
- 视频监控服务（每5分钟自动扫描）

### 停止服务

```powershell
.\lan_stop.ps1
```

### 查看评测进度

```powershell
python check_progress.py
```

**输出示例**：
```
评测进度总览（3人评测制）
--------------------------------------------------------------------------------
📊 任务完成情况:
  总任务数: 2239
  已完成（被评3次）: 450
  未完成: 1789
  完成率: 20.10%

📝 评分完成情况:
  需要评分总数: 6717 (=2239×3)
  已完成评分数: 1350
  还需评分数: 5367

👥 评审员进度:
  Judge-01: 145 (9.67%)
  Judge-02: 138 (9.20%)
  ...
```

### 导出评分数据

```powershell
.\export_all.ps1
```

**导出内容**：
- `export_results/ratings_long_<时间戳>.csv` - 长表格式
- `export_results/ratings_wide_<时间戳>.csv` - 宽表格式
- `export_results/summary_<时间戳>.txt` - 进度统计

### 查询特定视频状态

```powershell
python query_video_status.py <sample_id> <modelname>
```

**示例**：
```powershell
python query_video_status.py animals_001_single wan21
```

### 任务随机打散

如果发现同一参考视频的多个模型任务连续出现：

```powershell
.\lan_stop.ps1
python scripts\shuffle_pending_tasks.py
.\lan_start_with_monitor.ps1
```

---

## 🔧 监控功能

### 自动监控（推荐）

使用 `.\lan_start_with_monitor.ps1` 启动服务时，监控服务会自动运行。

**监控功能**：
- ✅ 每5分钟自动扫描 `video/genvideo/` 目录
- ✅ 检测新增视频 → 自动创建任务 → 自动分配给所有评审员
- ✅ 检测删除视频 → 清理未完成任务
- ✅ 保留所有已完成的评分（即使视频被删除）
- ✅ 新任务自动随机打散，避免顺序偏差

**监控窗口**：
- 窗口标题：`Video Monitor - Every 300 sec`
- 启动后立即执行第一次扫描（无需等待）
- 显示实时进度：`[1/4]` 到 `[4/4]`
- 显示检测到的新增/删除视频
- 显示任务更新统计

### 手动监控

```powershell
# 立即扫描一次
python scripts\simple_monitor.py --once

# 持续监控（前台运行）
python scripts\simple_monitor.py
```

### 新增模型支持

监控脚本**完全支持动态识别新模型**：

1. 在 `video/genvideo/` 下创建新模型文件夹（如 `newmodel/newmodel/`）
2. 放置视频文件（文件名必须匹配已有的sample_id）
3. 监控脚本自动识别并创建任务
4. 自动分配给所有评审员
5. 自动随机打散任务顺序

**无需修改任何代码！**

---

## 📊 评分维度

系统采用**四维度评分**，每个维度1-5分：

### 1. 基本语义对齐 (Semantic Alignment)
- 主体对象、属性、关系是否正确再现
- 是否有冗余/缺失/错误的对象

### 2. 运动 (Motion Quality)
- 主体/物体运动的方向、速度、轨迹
- 运动是否自然、流畅、无伪影

### 3. 事件时序一致性 (Temporal Consistency)
- 微事件的先后、重叠、包含关系
- 事件顺序是否正确、节奏是否合理

### 4. 世界知识与功能性真实度 (Realism)
- 是否符合常识、物理规律、因果关系
- 工具/物体的功能与用法是否合理

**详细评分规则**：见 `rule.txt` 文件

---

## 🐛 故障排除

### 端口占用

```powershell
# 查找占用端口的进程
netstat -ano | findstr "8502"

# 杀掉进程
taskkill /PID <PID> /F

# 重新启动
.\lan_start_with_monitor.ps1
```

### 视频无法加载

```powershell
# 重新准备数据
python scripts\prepare_data.py

# 重启服务
.\lan_stop.ps1
.\lan_start_with_monitor.ps1
```

### 进度显示错误

```powershell
# 检查数据库版本
python check_db_version.py

# 应显示：✅ V2系统（3人评测制）
```

### Prompt显示sample_id而不是文本

```powershell
# 修复Prompt文本
python scripts\fix_prompt_text.py

# 重启服务
.\lan_stop.ps1
.\lan_start_with_monitor.ps1
```

### 监控窗口看起来卡住

```powershell
# 可能正在处理大量数据，等待30秒观察输出
# 或按Ctrl+C停止，运行测试：
python scripts\monitor_new_videos.py --once
```

---

## 📝 开发指南

### 技术栈

- **前端**：Streamlit (Python)
- **后端**：Python 3.9+
- **数据库**：SQLite3 (WAL模式)
- **视频服务**：Python HTTP Server
- **并发控制**：SQLite WAL + Busy Timeout

### 数据库触发器

系统使用触发器自动维护任务状态：

1. **触发器1**：`update_task_on_rating_insert`
   - 评分插入时自动更新 `tasks.current_ratings`
   - 达到3次评分时自动标记 `tasks.completed = 1`

2. **触发器2**：`cleanup_assignments_on_task_complete`
   - 任务完成时自动删除未完成的 `assignments`
   - 保留已有评分的assignments（用户可能正在编辑）

### 添加新功能

1. Fork本项目
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -am 'Add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建Pull Request

---

## 📚 文档

- [快速启动指南](docs/快速启动.txt) - 中文
- [Quick Start](docs/QUICK_START.txt) - English
- [详细评分规则](rule.txt)
- [数据库结构](db/schema.sql)

---

## 🤝 贡献者

感谢所有为本项目做出贡献的人员！

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 📧 联系方式

如有问题或建议，请通过以下方式联系：

- **Issue**: [GitHub Issues](https://github.com/your-username/aiv-mos-v4/issues)
- **Email**: your-email@example.com

---

## 🙏 致谢

感谢所有参与评测的评审员和技术支持人员！

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by AI Video Research Team

</div>

