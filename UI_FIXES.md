# UI修复说明

## 修复的问题

### 1. ✅ 视频加载问题

**问题描述**：
- 提交评测后，新任务显示的仍然是旧视频
- 浏览器缓存导致视频未正确刷新

**解决方案**：

1. **添加任务ID跟踪**
   ```python
   # 保存当前任务ID，用于检测任务切换
   if st.session_state.current_task_id != task['task_id']:
       st.session_state.current_task_id = task['task_id']
       # 清空选择状态
   ```

2. **添加缓存破坏器（Cache Buster）**
   ```python
   cache_buster = int(time_module.time())
   video_url = f"{VIDEO_SERVER_BASE}/{video_path}?t={cache_buster}"
   ```
   - 在视频URL后添加时间戳参数
   - 强制浏览器重新加载视频

3. **使用唯一的key属性**
   ```html
   <video key="video_a_{task['task_id']}" ...>
   ```

4. **提交后清空任务ID**
   ```python
   st.session_state.current_task_id = None
   ```

### 2. ✅ 隐藏模型名称（盲评）

**问题描述**：
- 需要实现盲评，避免评审员受到模型名称的影响

**解决方案**：

1. **视频标签只显示"视频A"和"视频B"**
   ```python
   # 之前：视频A: {task["model_a"]}
   # 修改后：视频A
   st.markdown('<div class="model-label">视频A</div>')
   ```

2. **按钮不显示模型名**
   ```python
   # 之前：选择 视频A ({task['model_a']})
   # 修改后：选择 视频A
   st.button(f"{choice_a_style}选择 视频A")
   ```

3. **选择提示不显示模型名**
   ```python
   # 之前：当前选择：视频A (sora2)
   # 修改后：当前选择：视频A
   st.info(f"当前选择：**视频A**")
   ```

4. **侧边栏添加盲评说明**
   ```markdown
   **注意**：模型名称已隐藏（盲评）
   ```

**模型信息保留**：
- 数据库中仍然记录真实的模型名称
- 导出数据时可以查看模型对比结果
- 只在UI界面对评审员隐藏

## 技术细节

### 视频刷新机制

```python
# 1. 检测任务切换
if st.session_state.current_task_id != task['task_id']:
    # 清空所有相关状态
    st.session_state.current_task_id = task['task_id']
    st.session_state.temp_choice = None
    st.session_state.show_comment = False
    st.session_state.chosen_model = None

# 2. 添加时间戳强制刷新
cache_buster = int(time_module.time())
video_url = f"{url}?t={cache_buster}"

# 3. 提交成功后重置
st.session_state.current_task_id = None
st.rerun()
```

### 盲评实现

```python
# 内部保存真实模型名（用于数据库存储）
st.session_state.chosen_model = task['model_a']  # 真实模型名

# 显示给用户的信息
st.info(f"当前选择：**视频A**")  # 不显示模型名
```

## 测试建议

### 视频加载测试

1. 打开评测页面
2. 确认3个视频都自动播放
3. 提交评测
4. 检查新任务的视频是否正确加载（应该是不同的视频）
5. 多次提交，确认每次都正确切换

### 盲评测试

1. 检查页面上是否看不到任何模型名称
2. 只显示"视频A"和"视频B"
3. 提交后查看数据库，确认记录了真实模型名
4. 运行导出脚本，确认可以看到模型对比

```powershell
# 导出数据查看模型信息
.\export_all_compare.ps1

# 查看导出的CSV文件
# 应该包含model_a和model_b列
```

## 相关文件

修改的文件：
- `app/streamlit_app_compare.py` - UI主程序

导出脚本（可查看模型信息）：
- `scripts/export_ratings_compare.py`
- `check_progress_compare.py`

## 使用方法

```powershell
# 1. 停止旧服务
.\lan_stop_compare.ps1

# 2. 重新启动
.\lan_start_compare.ps1

# 3. 打开评审员链接测试
# 链接会自动显示在启动输出中
```

## 预期效果

### 视频加载
- ✅ 每个新任务都正确加载对应的3个视频
- ✅ 视频自动播放
- ✅ 无缓存问题

### 盲评
- ✅ 页面不显示任何模型名称
- ✅ 只显示"视频A"、"视频B"
- ✅ 数据库正确记录模型信息
- ✅ 导出数据包含模型对比

---

**修复完成时间**：2024年（当前）
**测试状态**：待测试

