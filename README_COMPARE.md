# AI视频生成比较评测系统 (Compare Mode)

<div align="center">

**基于两两比较的AI视频生成模型评测系统**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/)

</div>

---

## 📋 项目简介

本系统是原有打分评测系统的**比较评测版本**，采用**两两配对比较**的方式，让评审员选择更好的生成视频，避免主观打分的偏见。

### 🆚 与原系统的区别

| 特性 | 原系统（打分模式） | 新系统（比较模式） |
|------|-------------------|-------------------|
| **评测方式** | 4维度打分（1-5分） | 两两比较选择 |
| **UI布局** | 上下排列（参考+生成） | 左右分栏（左参考，右两个生成上下叠放） |
| **任务生成** | 每个生成视频一个任务 | 每对生成视频一个任务 |
| **数据库** | aiv_eval_v4.db | aiv_compare_v1.db |
| **端口** | 8502 (UI) + 8010 (视频) | 8503 (UI) + 8011 (视频) |
| **视频目录** | video/genvideo/ | video2/ |

### 🎯 核心特性

- **两两配对**：如果参考视频有N个生成视频，则生成C(N,2)个比较任务
- **三人评测制**：每个比较任务需3个不同评审员评测
- **共享任务池**：所有评审员共享任务，自动平衡工作量
- **动态监控**：支持运行时添加新模型和视频
- **独立运行**：与原打分系统完全独立，可同时运行

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.9+
- **操作系统**: Windows 10/11
- **网络**: 局域网环境
- **磁盘空间**: ~50GB

### 安装依赖

```powershell
# 使用原系统的依赖即可
pip install -r requirements.txt
```

### 首次部署

#### 1️⃣ 准备数据

```powershell
python scripts\prepare_data_compare.py
```

**功能**：
- 扫描 `video/refvideo/` 目录（参考视频）
- 扫描 `video2/` 目录（生成视频）
- 生成两两配对的比较任务清单
- 输出到 `data/comparison_tasks.csv`

**示例输出**：
```
📹 扫描参考视频...
   找到 1098 个参考视频

🤖 扫描生成视频（video2）...
   找到 3294 个生成视频
   覆盖 1098 个样本

   模型数量分布:
     3个模型: 1098个样本

⚙️  生成比较任务...
   ✅ 生成 3294 个比较任务  (1098 × C(3,2))
```

#### 2️⃣ 初始化数据库

```powershell
python scripts\setup_project_compare.py --judges 10
```

**功能**：
- 创建数据库 `aiv_compare_v1.db`
- 创建10个评审员账户
- 导入参考视频和生成视频
- 创建比较任务
- 为每个评审员随机分配任务

**参数**：
- `--judges 10`: 评审员数量（默认10）
- `--db aiv_compare_v1.db`: 数据库路径（可选）
- `--csv data/comparison_tasks.csv`: 任务清单（可选）

#### 3️⃣ 配置防火墙（可选）

```powershell
# 以管理员身份运行PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_firewall_compare.ps1
```

**功能**：开放端口8503（UI）和8011（视频服务）

#### 4️⃣ 启动服务

```powershell
.\lan_start_compare.ps1
```

**启动内容**：
- Streamlit UI（端口8503）
- 视频HTTP服务器（端口8011）
- 视频监控服务（每5分钟扫描）

**输出示例**：
```
============================================================
 比较评测模式 - 启动服务
============================================================

本机IP: 172.16.82.12

[1/3] 启动视频服务器 (端口 8011)...
  视频服务器已启动 (Job ID: 1)

[2/3] 启动Streamlit UI (端口 8503)...
  Streamlit UI已启动 (Job ID: 2)

[3/3] 启动监控服务 (每300秒扫描)...
  监控服务已启动 (Job ID: 3)

============================================================
 服务启动成功！
============================================================

访问地址:
  本机访问: http://localhost:8503/?uid=<评审员UID>
  局域网访问: http://172.16.82.12:8503/?uid=<评审员UID>
```

#### 5️⃣ 获取评审员链接

```powershell
python get_links_compare.py
```

**输出示例**：
```
============================================================
比较评测模式 - 评审员访问链接
============================================================

本机IP: 172.16.82.12
UI端口: 8503

============================================================

【Judge-01】
  本机访问: http://localhost:8503/?uid=abc123...
  局域网访问: http://172.16.82.12:8503/?uid=abc123...

【Judge-02】
  本机访问: http://localhost:8503/?uid=def456...
  局域网访问: http://172.16.82.12:8503/?uid=def456...

...
```

将链接分发给评审员即可开始评测！

---

## 📁 新增文件结构

```
AIGC/
├── db/
│   └── schema_compare.sql              # 比较模式数据库结构
├── app/
│   └── streamlit_app_compare.py        # 比较模式UI
├── scripts/
│   ├── prepare_data_compare.py         # 数据准备（扫描video2）
│   ├── setup_project_compare.py        # 项目初始化
│   ├── monitor_new_videos_compare.py   # 视频监控服务
│   ├── export_ratings_compare.py       # 导出评分数据
│   └── setup_firewall_compare.ps1      # 防火墙配置
├── data/
│   └── comparison_tasks.csv            # 比较任务清单
├── video2/                             # 生成视频目录（新）
│   ├── model1/model1/*.mp4
│   ├── model2/model2/*.mp4
│   └── ...
├── export_results_compare/             # 导出结果（新）
├── aiv_compare_v1.db                   # 比较模式数据库
├── lan_start_compare.ps1               # 启动脚本
├── lan_stop_compare.ps1                # 停止脚本
├── export_all_compare.ps1              # 导出脚本
├── check_progress_compare.py           # 进度查看
├── get_links_compare.py                # 获取评审员链接
└── README_COMPARE.md                   # 本文件
```

---

## 🎯 评测流程

### UI界面

```
┌─────────────────────────────────────────────────────────┐
│                    AI视频比较评测系统                     │
├─────────────────────────────────────────────────────────┤
│ 📝 视频描述：[显示Prompt文本]                            │
├───────────────────────┬─────────────────────────────────┤
│  🎯 参考视频          │  🤖 生成视频A: [模型名]         │
│  （真实世界视频）      │  [视频播放器]                   │
│  [视频播放器]         │                                 │
│                       │  🤖 生成视频B: [模型名]         │
│                       │  [视频播放器]                   │
├───────────────────────┴─────────────────────────────────┤
│ 🎯 请选择更好的生成视频：                                │
│  [✅ 选择视频A]  [✅ 选择视频B]  [🤷 两者相当]          │
└─────────────────────────────────────────────────────────┘
```

### 评测步骤

1. 评审员打开个人链接
2. 观看左侧的参考视频
3. 观看右侧上下叠放的两个生成视频
4. 点击按钮选择更好的一个（或选择"两者相当"）
5. 可选添加评论说明理由
6. 提交后自动进入下一个任务

### 任务完成条件

- 每个比较任务需要**3个不同评审员**评测
- 达到3次评测后，任务自动标记完成
- 完成的任务从所有评审员的列表中移除

---

## ⚙️ 日常操作

### 启动服务

```powershell
.\lan_start_compare.ps1
```

### 停止服务

```powershell
.\lan_stop_compare.ps1
```

### 查看评测进度

```powershell
python check_progress_compare.py
```

**输出示例**：
```
============================================================
比较评测模式 - 进度总览（3人评测制）
============================================================

📊 任务完成情况:
--------------------------------------------------------------------------------
  总任务数: 3294
  已完成（被评3次）: 450
  未完成: 2844
  完成率: 13.66%

📝 评测完成情况:
  需要评测总数: 9882 (=3294×3)
  已完成评测数: 1350
  还需评测数: 8532

👥 评审员进度:
  Judge-01: 145 (4.40%)
  Judge-02: 138 (4.19%)
  ...

🤖 模型比较统计:
  各模型参与的比较任务数:
    sora2: 2196 个任务
    cogfun: 2196 个任务
    kling: 2196 个任务

  模型胜率统计（已完成评测）:
    sora2: 520 次胜出
    cogfun: 480 次胜出
    kling: 300 次胜出
    平局: 50 次
```

### 导出评分数据

```powershell
.\export_all_compare.ps1
```

**导出文件**：
- `comparisons_long_<时间戳>.csv` - 详细评测记录（每行一个评测）
- `task_summary_<时间戳>.csv` - 任务汇总（每个任务的所有评测）
- `model_stats_<时间戳>.csv` - 模型统计（胜率等）
- `summary_<时间戳>.txt` - 进度摘要

---

## 🔧 监控功能

### 自动监控（推荐）

使用 `.\lan_start_compare.ps1` 启动时，监控服务会自动运行。

**监控功能**：
- ✅ 每5分钟自动扫描 `video2/` 目录
- ✅ 检测新增视频 → 自动创建比较任务
- ✅ 检测删除视频 → 清理未完成任务
- ✅ 新任务自动随机分配给所有评审员
- ✅ 支持动态添加新模型

### 手动监控

```powershell
# 立即扫描一次
python scripts\monitor_new_videos_compare.py --once

# 持续监控（前台运行）
python scripts\monitor_new_videos_compare.py --interval 300
```

### 添加新模型

完全支持动态添加新模型，无需修改代码：

1. 在 `video2/` 下创建新模型文件夹（如 `newmodel/newmodel/`）
2. 放置视频文件（文件名必须匹配已有的sample_id）
3. 监控脚本自动识别并创建比较任务
4. 自动分配给所有评审员

**示例**：
```
video2/
├── sora2/sora2/
│   ├── animals_001_single.mp4
│   ├── animals_002_multi.mp4
│   └── ...
├── cogfun/cogfun/
│   └── ...
└── newmodel/newmodel/        # 新添加的模型
    ├── animals_001_single.mp4
    └── ...
```

监控脚本会自动创建以下新任务：
- sora2 vs newmodel
- cogfun vs newmodel

---

## 📊 任务生成逻辑

### 配对规则

对于每个参考视频，如果有N个生成视频（N≥2），则生成 **C(N,2) = N×(N-1)/2** 个比较任务。

**示例**：

| 参考视频 | 生成视频 | 比较任务 | 任务数 |
|---------|---------|---------|-------|
| animals_001_single | sora2, cogfun | sora2 vs cogfun | 1 |
| food_005_multi | sora2, cogfun, kling | sora2 vs cogfun<br>sora2 vs kling<br>cogfun vs kling | 3 |
| sports_010_single | sora2, cogfun, kling, wan21 | sora2 vs cogfun<br>sora2 vs kling<br>sora2 vs wan21<br>cogfun vs kling<br>cogfun vs wan21<br>kling vs wan21 | 6 |

### 字母序约束

为避免重复，任务中 `model_a < model_b`（字母序），例如：
- ✅ `cogfun vs sora2`
- ❌ `sora2 vs cogfun`（不会创建）

---

## 🛠️ 数据库设计

### 核心表

- **judges** - 评审员信息
- **prompts** - 参考视频信息
- **videos** - 生成视频信息
- **tasks** - 比较任务（每个任务包含model_a和model_b）
- **assignments** - 任务分配（评审员×任务）
- **comparisons** - 比较结果（评审员的选择）

### 关键字段

**tasks表**：
```sql
task_id             -- 任务ID
sample_id           -- 参考视频ID
model_a             -- 模型A名称
model_b             -- 模型B名称
video_a_id          -- 模型A的视频ID
video_b_id          -- 模型B的视频ID
completed           -- 是否完成（0/1）
current_ratings     -- 当前评测次数（0-3）
```

**comparisons表**：
```sql
comparison_id       -- 评测ID
task_id             -- 任务ID
judge_id            -- 评审员ID
chosen_model        -- 选择的模型（model_a / model_b / tie）
comment             -- 可选评论
rating_time         -- 评测时间
```

### 触发器

1. **update_task_on_comparison_insert**
   - 评测插入时自动更新 `current_ratings`
   - 达到3次时自动标记 `completed = 1`

2. **cleanup_assignments_on_task_complete**
   - 任务完成时自动删除未评测的分配记录

---

## 🐛 故障排除

### 端口占用

```powershell
# 查找占用端口的进程
netstat -ano | findstr "8503"
netstat -ano | findstr "8011"

# 杀掉进程
taskkill /PID <PID> /F

# 或直接运行停止脚本
.\lan_stop_compare.ps1
```

### 视频无法加载

```powershell
# 检查video2目录是否存在
ls video2

# 重新准备数据
python scripts\prepare_data_compare.py

# 重启服务
.\lan_stop_compare.ps1
.\lan_start_compare.ps1
```

### 没有任务显示

可能原因：
1. 所有任务已完成
2. 数据库未初始化
3. video2目录中没有足够的视频（需要每个sample_id至少2个模型）

```powershell
# 检查进度
python check_progress_compare.py

# 检查数据库
python -c "import sqlite3; conn = sqlite3.connect('aiv_compare_v1.db'); print('任务数:', conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0])"
```

---

## 📈 导出数据格式

### comparisons_long_*.csv（详细记录）

| 字段 | 说明 |
|-----|------|
| comparison_id | 评测ID |
| task_id | 任务ID |
| sample_id | 参考视频ID |
| category | 类别 |
| prompt_text | Prompt文本 |
| model_a | 模型A名称 |
| model_b | 模型B名称 |
| judge_id | 评审员ID |
| judge_name | 评审员名称 |
| chosen_model | 选择的模型 |
| comment | 评论 |
| rating_time | 评测时间 |

### task_summary_*.csv（任务汇总）

| 字段 | 说明 |
|-----|------|
| task_id | 任务ID |
| sample_id | 参考视频ID |
| category | 类别 |
| model_a | 模型A名称 |
| model_b | 模型B名称 |
| completed | 是否完成 |
| current_ratings | 评测次数 |
| judges | 评审员列表 |
| choices | 选择列表 |
| model_a_wins | 模型A胜出次数 |
| model_b_wins | 模型B胜出次数 |
| ties | 平局次数 |

### model_stats_*.csv（模型统计）

| 字段 | 说明 |
|-----|------|
| model_name | 模型名称 |
| win_count | 胜出次数 |
| total_tasks | 参与的总任务数 |
| completed_tasks | 完成的任务数 |
| win_rate | 胜率（%） |

---

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- **Issue**: [GitHub Issues](https://github.com/hang23303051/AIGC/issues)
- **Email**: qihang6@mail2.sysu.edu.cn

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by AI Video Research Team

</div>

