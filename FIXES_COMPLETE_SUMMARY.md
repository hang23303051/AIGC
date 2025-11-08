# 问题修复完整总结

## ✅ 已修复的三个问题

### 问题 1：局域网视频加载失败 🌐

**根本原因**：
```python
# 原代码（错误）
VIDEO_SERVER_BASE = "http://localhost:8011"
```
- `localhost` 只能本机访问
- 局域网其他设备无法加载视频

**解决方案**：
```python
# 修复后（动态获取IP）
import socket

def get_server_ip():
    """获取服务器IP地址"""
    try:
        # 尝试获取局域网IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

SERVER_IP = get_server_ip()
VIDEO_SERVER_BASE = f"http://{SERVER_IP}:8011"
```

**工作原理**：
1. 创建一个UDP套接字
2. 尝试连接到外部地址（8.8.8.8）
3. 获取本地网络接口的IP地址
4. 使用该IP构建视频服务器URL

**配合修改**：
```powershell
# lan_start_compare.ps1 中已添加
python -m http.server 8011 --bind 0.0.0.0 --directory .
```

---

### 问题 2：返回上一题逻辑错误 ⬅️

**原问题**：
- 只能返回一次，无法持续往前翻
- 没有"下一题"功能
- 逻辑混乱

**解决方案**：使用历史索引导航

#### 核心概念：
```
history_index = -1  →  当前任务（未评）
history_index = 0   →  最近一次已评任务
history_index = 1   →  倒数第二次已评任务
history_index = 2   →  倒数第三次已评任务
...
```

#### 新增函数：

```python
def get_current_task(judge_id):
    """获取当前未评任务"""
    # 获取第一个未评任务
    ...

def get_history_task(judge_id, history_index):
    """获取历史任务（用于返回上一题）
    history_index: 历史索引，0=最近一次，1=倒数第二次，以此类推
    """
    # 获取第 history_index 个历史任务
    ...

def get_completed_count(judge_id):
    """获取已完成任务数量"""
    # 返回已完成的任务总数
    ...
```

#### 导航界面：

```
┌─────────────┬─────────────┬──────────────────────────────────┐
│ ⬅️ 上一题   │ ➡️ 下一题   │ 🔄 重判模式 | 第 2/5 题           │
└─────────────┴─────────────┴──────────────────────────────────┘
```

**功能特性**：
1. ✅ **持续返回**：可以一直点击"上一题"，查看所有历史任务
2. ✅ **前进导航**：点击"下一题"返回更新的任务
3. ✅ **位置提示**：显示当前位置（如"第 2/5 题"）
4. ✅ **重判功能**：显示之前的选择，可以修改
5. ✅ **智能禁用**：到达边界时自动禁用按钮

**使用流程**：
```
当前任务 → 点击"上一题" → 历史任务1 → 点击"上一题" → 历史任务2 → ...
                           ↑                    ↑
                      可以修改选择         可以继续往前翻
                           ↓                    ↓
                    点击"下一题"           点击"下一题"
```

---

### 问题 3：快捷键失效 ⌨️

**原问题**：
- JavaScript 注入不稳定
- 事件监听器丢失
- iframe 方案不可靠

**解决方案**：使用数字键 + IIFE + 事件清理

#### 快捷键映射（改进）：
```
数字键 1  →  选择视频A
数字键 2  →  选择视频B
数字键 3  →  两者相当
```

**为什么改用数字键？**
- ✅ 更直观（1、2、3 对应 A、B、相当）
- ✅ 避免与浏览器快捷键冲突（A/S/D可能被占用）
- ✅ 单手操作更方便（数字键在键盘顶部）

#### 实现代码：

```javascript
(function() {
    // 移除之前的监听器（避免重复）
    if (window.keydownHandler) {
        document.removeEventListener('keydown', window.keydownHandler);
    }
    
    // 创建新的监听器
    window.keydownHandler = function(e) {
        // 只在没有焦点在输入框时响应
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // 获取所有按钮
        const buttons = Array.from(document.querySelectorAll('button'));
        
        if (e.key === '1') {
            const btnA = buttons.find(btn => btn.textContent.includes('选择 视频A'));
            if (btnA && !btnA.disabled) {
                btnA.click();
                e.preventDefault();
            }
        }
        // ... 2 和 3 类似
    };
    
    // 添加监听器
    document.addEventListener('keydown', window.keydownHandler, true);
})();
```

**技术要点**：
1. **IIFE（立即执行函数）**：避免全局变量污染
2. **事件清理**：每次重新绑定前先移除旧监听器
3. **按钮查找**：通过文本内容动态查找按钮
4. **禁用检查**：避免点击禁用的按钮
5. **阻止默认行为**：防止浏览器默认行为干扰

**侧边栏提示**：
```markdown
### ⌨️ 快捷键

- **数字键 1** → 选择视频A
- **数字键 2** → 选择视频B
- **数字键 3** → 两者相当
```

---

## 📊 修改文件总览

### 主要修改：`app/streamlit_app_compare.py`

| 行号 | 修改内容 | 说明 |
|------|----------|------|
| 14 | 添加 `import socket` | 支持获取IP地址 |
| 20-34 | 添加 `get_server_ip()` 函数 | 动态获取服务器IP |
| 34 | 修改 `VIDEO_SERVER_BASE` | 使用动态IP |
| 176-210 | 简化 `get_current_task()` | 只获取未评任务 |
| 213-251 | 新增 `get_history_task()` | 获取历史任务 |
| 254-265 | 新增 `get_completed_count()` | 统计已完成数 |
| 346-351 | 侧边栏添加快捷键说明 | 用户提示 |
| 366-423 | 重写 `show_task()` 函数 | 支持历史导航 |
| 387-423 | 添加导航栏UI | 上一题/下一题按钮 |
| 479-568 | 简化选择按钮逻辑 | 移除旧的导航按钮 |
| 570-617 | 添加快捷键JavaScript | 数字键支持 |
| 636-664 | 重写 `main()` 函数 | 历史索引导航 |

---

## 🧪 测试步骤

### 1. 测试局域网视频加载

```powershell
# 1. 重启服务
.\lan_stop_compare.ps1
.\lan_start_compare.ps1

# 2. 记录显示的网络地址
# 例如：http://192.168.1.100:8503/?uid=xxx

# 3. 在本机测试
# 打开浏览器访问，视频应该正常加载

# 4. 在同一局域网的其他设备测试
# 手机/平板/其他电脑访问相同地址
# ✅ 视频应该能正常加载和播放
```

**验证点**：
- ✅ 本机访问正常
- ✅ 局域网其他设备访问正常
- ✅ 三个视频都能加载
- ✅ 视频能正常播放

---

### 2. 测试持续返回上一题

```
操作步骤：
1. 完成 3-5 个评测任务
2. 点击"⬅️ 上一题"按钮
3. 应该看到最近评测的任务
4. 继续点击"⬅️ 上一题"
5. 应该能持续往前翻
6. 点击"➡️ 下一题"
7. 应该返回到更新的任务
8. 修改某个历史任务的选择
9. 提交后应该返回当前任务
```

**验证点**：
- ✅ 可以持续返回上一题
- ✅ 显示位置信息（如"第 2/5 题"）
- ✅ 显示之前的选择
- ✅ 可以修改历史评测
- ✅ 边界禁用正确（到头时按钮变灰）
- ✅ 提交后返回当前任务

---

### 3. 测试快捷键

```
操作步骤：
1. 进入评测页面
2. 观看视频
3. 按键盘数字键：
   - 按 1 → 应该选择视频A并提交
   - 按 2 → 应该选择视频B并提交
   - 按 3 → 应该选择两者相当并提交
4. 每次提交后自动跳转到下一题
```

**验证点**：
- ✅ 数字键 1 选择视频A
- ✅ 数字键 2 选择视频B
- ✅ 数字键 3 选择两者相当
- ✅ 提交后自动跳转
- ✅ 侧边栏显示快捷键说明

---

## 🎯 使用建议

### 高效评测工作流

```
1. 打开评审员链接
   ↓
2. 三个视频自动播放
   ↓
3. 观看对比后，按数字键快速选择
   ↓
4. 自动提交并跳转
   ↓
5. 重复步骤 2-4
```

### 快捷键记忆技巧

```
数字键位置：
[1] [2] [3] [4] [5] ...
 ↓   ↓   ↓
 A   B  相当

顺序对应：
1 = 第一个视频 = 视频A
2 = 第二个视频 = 视频B
3 = 第三个选项 = 两者相当
```

### 历史导航技巧

```
场景1：想查看刚才的评测
→ 点击"⬅️ 上一题"

场景2：想修改之前某个评测
→ 持续点击"⬅️ 上一题"找到目标任务
→ 重新选择
→ 提交（自动返回当前任务）

场景3：翻过头了
→ 点击"➡️ 下一题"回到更新的任务
```

---

## 🔧 技术架构

### 历史导航系统

```
Session State:
├── history_index: int
│   ├── -1  : 当前任务（未评）
│   ├── 0   : 最近一次历史
│   ├── 1   : 倒数第二次历史
│   └── N-1 : 第一次历史
│
├── current_task_id: int
│   └── 用于检测任务切换
│
└── judge_id: int
    └── 当前评审员ID

Database Queries:
├── get_current_task()
│   └── SELECT ... WHERE NOT EXISTS (已评) ORDER BY position LIMIT 1
│
├── get_history_task(history_index)
│   └── SELECT ... WHERE EXISTS (已评) ORDER BY rating_time DESC LIMIT 1 OFFSET history_index
│
└── get_completed_count()
    └── SELECT COUNT(*) FROM comparisons WHERE judge_id = ?
```

### 视频服务器架构

```
启动流程:
┌─────────────────────────────────────┐
│ 1. 获取本机局域网IP                 │
│    (使用socket.connect方法)         │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 2. 启动HTTP服务器                   │
│    python -m http.server 8011       │
│    --bind 0.0.0.0 --directory .     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 3. Streamlit UI使用实际IP           │
│    VIDEO_SERVER_BASE =              │
│    f"http://{SERVER_IP}:8011"       │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 4. 所有设备都能访问视频             │
│    本机: http://192.168.1.100:8011  │
│    手机: http://192.168.1.100:8011  │
└─────────────────────────────────────┘
```

---

## 📝 配置检查清单

启动前确认：

- [ ] 已停止旧服务 (`.\lan_stop_compare.ps1`)
- [ ] 防火墙规则已设置 (`.\scripts\setup_firewall_compare.ps1`)
- [ ] 数据库文件存在 (`aiv_compare_v1.db`)
- [ ] 视频文件夹存在且有视频
- [ ] 本机网络正常（非 169.254.x.x）

启动后验证：

- [ ] 视频服务器在 8011 端口
- [ ] Streamlit UI 在 8503 端口
- [ ] 显示正确的局域网IP地址
- [ ] 评审员链接可访问
- [ ] 视频正常加载

---

## 🚨 常见问题

### Q1: 快捷键还是不工作？

**解决方案**：
1. 强制刷新浏览器（Ctrl+Shift+R / Cmd+Shift+R）
2. 清除浏览器缓存
3. 确保焦点不在输入框中
4. 尝试其他浏览器（推荐Chrome/Edge）

### Q2: 视频还是加载不了？

**检查步骤**：
```powershell
# 1. 检查服务器IP
python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0])"

# 2. 检查8011端口
netstat -ano | findstr "8011"

# 3. 检查防火墙
Get-NetFirewallRule -DisplayName "*8011*"

# 4. 测试视频服务器
# 在浏览器访问: http://你的IP:8011/
```

### Q3: 返回上一题显示空白？

**可能原因**：
- 还没有完成任何任务
- 数据库连接问题

**解决方案**：
```powershell
# 检查已完成任务数
python -c "import sqlite3; conn = sqlite3.connect('aiv_compare_v1.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM comparisons WHERE judge_id = 1'); print(cursor.fetchone()[0])"
```

---

## ✅ 完成状态

| 功能 | 状态 | 测试 |
|------|------|------|
| 局域网视频加载 | ✅ 完成 | 待测试 |
| 持续返回上一题 | ✅ 完成 | 待测试 |
| 快捷键支持 | ✅ 完成 | 待测试 |
| 导航UI | ✅ 完成 | 待测试 |
| 重判功能 | ✅ 完成 | 待测试 |

---

**所有问题已修复！请重启服务并进行全面测试。** 🎉

