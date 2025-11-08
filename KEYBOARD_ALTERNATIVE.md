# 快捷键备用方案

## 当前实现

当前使用 `components.html` 创建隐藏输入框来捕获键盘事件。

## 如果快捷键仍然不工作，可以尝试以下备用方案：

### 方案 1：使用 streamlit-keyup 库（推荐）

这是专门为 Streamlit 设计的键盘事件库。

#### 安装步骤：

```powershell
# 1. 停止服务
.\lan_stop_compare.ps1

# 2. 安装库
pip install streamlit-keyup

# 3. 重启服务
.\lan_start_compare.ps1
```

#### 修改代码：

在 `app/streamlit_app_compare.py` 文件开头添加导入：

```python
from st_keyup import st_keyup
```

在 `show_task()` 函数中，替换快捷键部分为：

```python
# 使用 streamlit-keyup 监听按键
if 'last_key' not in st.session_state:
    st.session_state.last_key = None

key_pressed = st_keyup("", key="keyboard_input", placeholder="按 1/2/3 快速选择")

if key_pressed:
    if key_pressed == '1' and not is_review:
        # 选择视频A
        if is_review:
            delete_comparison(task['task_id'], st.session_state.judge_id)
        
        success = submit_comparison(
            task['task_id'],
            st.session_state.judge_id,
            task['model_a'],
            ""
        )
        
        if success:
            st.session_state.history_index = -1
            st.rerun()
    
    elif key_pressed == '2' and not is_review:
        # 选择视频B
        if is_review:
            delete_comparison(task['task_id'], st.session_state.judge_id)
        
        success = submit_comparison(
            task['task_id'],
            st.session_state.judge_id,
            task['model_b'],
            ""
        )
        
        if success:
            st.session_state.history_index = -1
            st.rerun()
    
    elif key_pressed == '3' and not is_review:
        # 两者相当
        if is_review:
            delete_comparison(task['task_id'], st.session_state.judge_id)
        
        success = submit_comparison(
            task['task_id'],
            st.session_state.judge_id,
            "tie",
            ""
        )
        
        if success:
            st.session_state.history_index = -1
            st.rerun()
```

---

### 方案 2：禁用快捷键

如果快捷键功能不是必须的，可以简单地删除快捷键代码：

在 `app/streamlit_app_compare.py` 中，找到并删除：

```python
# 添加快捷键支持（通过隐藏输入框捕获按键）
keyboard_listener_html = """
...
"""
components.html(keyboard_listener_html, height=1, width=1)
```

然后在侧边栏也删除快捷键说明。

---

### 方案 3：使用浏览器插件

安装浏览器快捷键插件（如 Shortkeys for Chrome），手动配置快捷键。

**Chrome 插件推荐**：
- Shortkeys (Custom Keyboard Shortcuts)
- Keyboard Shortcuts to Reorder Tabs

**配置示例**：
- 按 `1` → 模拟点击"选择 视频A"按钮
- 按 `2` → 模拟点击"选择 视频B"按钮
- 按 `3` → 模拟点击"两者相当"按钮

---

## 调试快捷键

如果想检查当前快捷键是否工作：

1. 打开浏览器开发者工具（F12）
2. 切换到 Console 标签
3. 按数字键 1、2、3
4. 查看是否有日志输出：
   - `Key pressed: 1`
   - `Clicking button: 选择 视频A`

如果看到这些日志，说明快捷键已经捕获，但可能点击失败。
如果没有日志，说明快捷键没有被捕获。

---

## 推荐方案总结

| 方案 | 难度 | 可靠性 | 推荐度 |
|------|------|--------|--------|
| streamlit-keyup库 | ⭐ 简单 | ⭐⭐⭐⭐⭐ 非常高 | ⭐⭐⭐⭐⭐ 强烈推荐 |
| 禁用快捷键 | ⭐ 非常简单 | ⭐⭐⭐⭐⭐ 不会出错 | ⭐⭐⭐ 如果不需要快捷键 |
| 浏览器插件 | ⭐⭐ 中等 | ⭐⭐⭐ 中等 | ⭐⭐ 临时方案 |
| 当前实现 | - | ⭐⭐⭐ 取决于浏览器 | ⭐⭐⭐ 先尝试 |

---

## 联系与支持

如果以上方案都不行，请提供以下信息：

1. 浏览器类型和版本
2. 操作系统
3. 浏览器控制台的错误信息
4. 是否看到任何键盘相关的日志

这将帮助诊断问题。

