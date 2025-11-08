#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI视频生成比较评测系统 - Streamlit UI
左侧显示参考视频，右侧上下叠放两个生成视频
评审员选择更好的一个
"""

import streamlit as st
import streamlit.components.v1 as components
import sqlite3
from pathlib import Path
import time
import socket

# 配置
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "aiv_compare_v1.db"

# 动态获取服务器IP（支持局域网访问）
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

# 页面配置
st.set_page_config(
    page_title="AI视频比较评测系统",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS样式
st.markdown("""
<style>
    .video-container {
        border: 3px solid #ddd;
        border-radius: 12px;
        padding: 10px;
        margin: 10px 0;
        background-color: #f9f9f9;
    }
    .ref-video-container {
        background-color: #e8f4f8;
        border-color: #2196F3;
        max-width: 800px;
        margin: 10px auto;
    }
    .gen-video-container {
        background-color: #fff8e1;
        border-color: #FF9800;
    }
    .model-label {
        font-size: 1.1em;
        font-weight: bold;
        color: #333;
        margin: 5px 0;
        text-align: center;
    }
    .prompt-box {
        background-color: #f0f7ff;
        border: 2px solid #4CAF50;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        font-size: 1.05em;
    }
    
    /* Video size control */
    video {
        max-height: 350px;
        width: 100%;
        object-fit: contain;
    }
    
    .ref-video-container video {
        max-height: 300px;
    }
    
    .gen-video-container video {
        max-height: 280px;
    }
    
    /* Custom button styling */
    div[data-testid="column"] > div > div > button {
        width: 100%;
        height: 60px;
        font-size: 1.05em;
        font-weight: bold;
        background-color: white !important;
        color: #333 !important;
        border: 3px solid #ddd !important;
        border-radius: 10px !important;
        transition: all 0.3s ease;
    }
    
    div[data-testid="column"] > div > div > button:hover {
        border-color: #FF5252 !important;
        transform: scale(1.02);
    }
    
    /* Selected button style */
    .selected-button {
        background-color: #FF5252 !important;
        color: white !important;
        border-color: #FF5252 !important;
    }
    
    /* Compact layout */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    h1 {
        margin-top: 0;
        margin-bottom: 0.5rem;
    }
    
    h3 {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    /* Keyboard shortcut hint */
    .shortcut-hint {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        font-size: 0.9em;
        z-index: 1000;
    }
</style>
""", unsafe_allow_html=True)

# 快捷键提示已移至侧边栏


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def verify_judge(uid):
    """验证评审员UID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT judge_id, judge_name FROM judges WHERE uid = ?", (uid,))
    result = cursor.fetchone()
    conn.close()
    return result


def get_current_task(judge_id):
    """获取当前未评任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            t.task_id,
            t.sample_id,
            t.model_a,
            t.model_b,
            t.current_ratings,
            p.prompt_text,
            p.category,
            p.ref_video_path,
            va.video_path as video_a_path,
            vb.video_path as video_b_path,
            a.position
        FROM assignments a
        JOIN tasks t ON a.task_id = t.task_id
        JOIN prompts p ON t.sample_id = p.sample_id
        JOIN videos va ON t.video_a_id = va.video_id
        JOIN videos vb ON t.video_b_id = vb.video_id
        WHERE a.judge_id = ?
        AND NOT EXISTS (
            SELECT 1 FROM comparisons c 
            WHERE c.task_id = t.task_id AND c.judge_id = ?
        )
        ORDER BY a.position ASC
        LIMIT 1
    """, (judge_id, judge_id))
    
    result = cursor.fetchone()
    conn.close()
    return result


def get_history_task(judge_id, history_index):
    """获取历史任务（用于返回上一题）
    history_index: 历史索引，0=最近一次，1=倒数第二次，以此类推
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            t.task_id,
            t.sample_id,
            t.model_a,
            t.model_b,
            t.current_ratings,
            p.prompt_text,
            p.category,
            p.ref_video_path,
            va.video_path as video_a_path,
            vb.video_path as video_b_path,
            a.position,
            c.chosen_model
        FROM assignments a
        JOIN tasks t ON a.task_id = t.task_id
        JOIN prompts p ON t.sample_id = p.sample_id
        JOIN videos va ON t.video_a_id = va.video_id
        JOIN videos vb ON t.video_b_id = vb.video_id
        LEFT JOIN comparisons c ON c.task_id = t.task_id AND c.judge_id = a.judge_id
        WHERE a.judge_id = ?
        AND EXISTS (
            SELECT 1 FROM comparisons c2 
            WHERE c2.task_id = t.task_id AND c2.judge_id = ?
        )
        ORDER BY c.rating_time DESC
        LIMIT 1 OFFSET ?
    """, (judge_id, judge_id, history_index))
    
    result = cursor.fetchone()
    conn.close()
    return result


def get_completed_count(judge_id):
    """获取已完成任务数量"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) 
        FROM comparisons 
        WHERE judge_id = ?
    """, (judge_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def delete_comparison(task_id, judge_id):
    """删除评测记录（用于重判）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM comparisons 
            WHERE task_id = ? AND judge_id = ?
        """, (task_id, judge_id))
        conn.commit()
        success = True
    except:
        success = False
    finally:
        conn.close()
    
    return success


def get_progress(judge_id):
    """获取评审员进度"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 总分配任务数
    cursor.execute("""
        SELECT COUNT(*) FROM assignments WHERE judge_id = ?
    """, (judge_id,))
    total_assigned = cursor.fetchone()[0]
    
    # 已完成任务数
    cursor.execute("""
        SELECT COUNT(*) FROM comparisons WHERE judge_id = ?
    """, (judge_id,))
    completed = cursor.fetchone()[0]
    
    conn.close()
    return completed, total_assigned


def submit_comparison(task_id, judge_id, chosen_model, comment=""):
    """提交比较结果"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO comparisons (task_id, judge_id, chosen_model, comment)
            VALUES (?, ?, ?, ?)
        """, (task_id, judge_id, chosen_model, comment))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    
    return success


def show_sidebar(judge_name, completed, total_assigned):
    """显示侧边栏"""
    with st.sidebar:
        st.title("🎬 视频比较评测")
        st.markdown("---")
        
        st.subheader(f"👤 {judge_name}")
        
        st.markdown("### 📊 评测进度")
        progress = completed / total_assigned if total_assigned > 0 else 0
        st.progress(progress)
        st.write(f"**{completed}** / {total_assigned} ({progress*100:.1f}%)")
        
        remaining = total_assigned - completed
        st.info(f"还剩 **{remaining}** 个任务")
        
        st.markdown("---")
        st.markdown("### 📋 评测说明")
        st.markdown("""
        1. 观看上方的**参考视频**
        2. 观看下方的**两个AI生成视频**
        3. 选择你认为**更好的生成视频**
        4. 点击对应的按钮提交
        
        **评价标准**：
        - 语义对齐度
        - 运动质量
        - 时序一致性  
        - 真实度
        
        **注意**：模型名称已隐藏（盲评）
        
        ---
        
        ### ⌨️ 快捷键
        
        **评分操作**：
        - **A** = 选择视频A
        - **W** = 选择视频B
        - **D** = 两者相当
        
        **导航操作**：
        - **Q** = 上一题
        - **E** = 下一题
        """)


def show_task(task, is_review=False, history_index=-1, max_history=0):
    """显示当前任务
    is_review: 是否为重判模式
    history_index: 历史索引位置
    max_history: 最大历史数量
    """
    # 保存当前任务ID，用于检测任务切换
    if 'current_task_id' not in st.session_state:
        st.session_state.current_task_id = None
    
    # 如果任务切换了，清空选择状态
    if st.session_state.current_task_id != task['task_id']:
        st.session_state.current_task_id = task['task_id']
        st.session_state.temp_choice = None
        st.session_state.show_comment = False
        st.session_state.chosen_model = None
    
    # 显示历史导航栏
    if is_review or max_history > 0:
        nav_cols = st.columns([1, 1, 3])
        
        with nav_cols[0]:
            # 上一题按钮
            if history_index < max_history - 1:
                if st.button("⬅️ 上一题", key="btn_prev_nav", use_container_width=True):
                    st.session_state.history_index += 1
                    st.session_state.current_task_id = None
                    st.rerun()
            else:
                st.button("⬅️ 上一题", key="btn_prev_nav_disabled", disabled=True, use_container_width=True)
        
        with nav_cols[1]:
            # 下一题按钮
            if history_index > -1:
                if st.button("➡️ 下一题", key="btn_next_nav", use_container_width=True):
                    st.session_state.history_index -= 1
                    st.session_state.current_task_id = None
                    st.rerun()
            else:
                st.button("➡️ 下一题", key="btn_next_nav_disabled", disabled=True, use_container_width=True)
        
        with nav_cols[2]:
            if is_review:
                # sqlite3.Row 对象访问方式
                try:
                    previous_choice = task['chosen_model'] if 'chosen_model' in task.keys() else None
                except:
                    previous_choice = None
                
                if previous_choice:
                    choice_text = "视频A" if previous_choice == task['model_a'] else ("视频B" if previous_choice == task['model_b'] else "两者相当")
                    position_text = f"第 {max_history - history_index}/{max_history} 题"
                    st.info(f"🔄 重判模式 | {position_text} | 之前选择：**{choice_text}**")
                else:
                    st.info("🔄 重判模式")
            else:
                if max_history > 0:
                    st.info(f"📊 已完成 {max_history} 题 | 点击左侧按钮可返回上一题查看/修改")
    
    # 显示Prompt（紧凑版）
    st.markdown(f"""
    <div class="prompt-box">
        <strong>📝 描述：</strong>{task['prompt_text']}
    </div>
    """, unsafe_allow_html=True)
    
    # 上方：参考视频（居中，限制宽度）
    st.markdown("#### 🎯 参考视频")
    st.markdown('<div class="video-container ref-video-container">', unsafe_allow_html=True)
    ref_video_url = f"{VIDEO_SERVER_BASE}/{task['ref_video_path']}"
    
    # 使用唯一key强制刷新视频
    import time as time_module
    cache_buster = int(time_module.time())
    
    st.markdown(f"""
    <video key="ref_{task['task_id']}" width="100%" controls autoplay loop muted>
        <source src="{ref_video_url}?t={cache_buster}" type="video/mp4">
    </video>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 下方：两个生成视频左右并排（隐藏模型名）
    st.markdown("#### 🤖 AI生成视频")
    col_a, col_b = st.columns(2)
    
    # 左侧：生成视频A（隐藏模型名）
    with col_a:
        st.markdown('<div class="video-container gen-video-container">', unsafe_allow_html=True)
        st.markdown('<div class="model-label">视频A</div>', unsafe_allow_html=True)
        video_a_url = f"{VIDEO_SERVER_BASE}/{task['video_a_path']}"
        st.markdown(f"""
        <video key="video_a_{task['task_id']}" width="100%" controls autoplay loop muted>
            <source src="{video_a_url}?t={cache_buster}" type="video/mp4">
        </video>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 右侧：生成视频B（隐藏模型名）
    with col_b:
        st.markdown('<div class="video-container gen-video-container">', unsafe_allow_html=True)
        st.markdown('<div class="model-label">视频B</div>', unsafe_allow_html=True)
        video_b_url = f"{VIDEO_SERVER_BASE}/{task['video_b_path']}"
        st.markdown(f"""
        <video key="video_b_{task['task_id']}" width="100%" controls autoplay loop muted>
            <source src="{video_b_url}?t={cache_buster}" type="video/mp4">
        </video>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 选择按钮（紧凑版）
    st.markdown("#### 🎯 请选择更好的视频：")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("选择 视频A", 
                     key="btn_a", use_container_width=True):
            # 如果是重判模式，先删除旧记录
            if is_review:
                delete_comparison(task['task_id'], st.session_state.judge_id)
            
            # 直接提交，不需要备注
            success = submit_comparison(
                task['task_id'],
                st.session_state.judge_id,
                task['model_a'],
                ""
            )
            
            if success:
                st.success("✅ 提交成功！正在加载下一个任务...")
                # 清空状态，准备下一个任务
                st.session_state.chosen_model = None
                st.session_state.temp_choice = None
                st.session_state.current_task_id = None
                st.session_state.history_index = -1  # 返回当前任务
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ 提交失败")
    
    with col2:
        if st.button("选择 视频B", 
                     key="btn_b", use_container_width=True):
            # 如果是重判模式，先删除旧记录
            if is_review:
                delete_comparison(task['task_id'], st.session_state.judge_id)
            
            # 直接提交，不需要备注
            success = submit_comparison(
                task['task_id'],
                st.session_state.judge_id,
                task['model_b'],
                ""
            )
            
            if success:
                st.success("✅ 提交成功！正在加载下一个任务...")
                # 清空状态，准备下一个任务
                st.session_state.chosen_model = None
                st.session_state.temp_choice = None
                st.session_state.current_task_id = None
                st.session_state.history_index = -1  # 返回当前任务
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ 提交失败")
    
    with col3:
        if st.button("两者相当", 
                     key="btn_tie", use_container_width=True):
            # 如果是重判模式，先删除旧记录
            if is_review:
                delete_comparison(task['task_id'], st.session_state.judge_id)
            
            # 直接提交，不需要备注
            success = submit_comparison(
                task['task_id'],
                st.session_state.judge_id,
                "tie",
                ""
            )
            
            if success:
                st.success("✅ 提交成功！正在加载下一个任务...")
                # 清空状态，准备下一个任务
                st.session_state.chosen_model = None
                st.session_state.temp_choice = None
                st.session_state.current_task_id = None
                st.session_state.history_index = -1  # 返回当前任务
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("❌ 提交失败")
    
    # 添加快捷键支持（通过隐藏输入框捕获按键）
    keyboard_listener_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #keyListener {
                position: fixed;
                bottom: 0;
                left: 0;
                opacity: 0;
                width: 1px;
                height: 1px;
                border: none;
                outline: none;
                pointer-events: none;
            }
        </style>
    </head>
    <body>
        <input id="keyListener" type="text" autocomplete="off">
        <script>
            const doc = window.parent.document;
            const input = document.getElementById('keyListener');
            
            // 确保输入框始终获得焦点
            function ensureFocus() {
                if (document.activeElement !== input) {
                    input.focus();
                }
            }
            
            // 每100ms检查一次焦点
            setInterval(ensureFocus, 100);
            ensureFocus();
            
            // 查找并点击按钮
            function findAndClickButton(text) {
                const buttons = Array.from(doc.querySelectorAll('button'));
                for (let btn of buttons) {
                    if (btn.textContent && btn.textContent.includes(text) && !btn.disabled) {
                        console.log('Clicking button:', text);
                        btn.click();
                        return true;
                    }
                }
                return false;
            }
            
            // 监听按键
            input.addEventListener('keydown', function(e) {
                const key = e.key.toLowerCase();
                console.log('Key pressed:', key);
                
                let handled = false;
                
                // 选择按钮
                if (key === 'a') {
                    handled = findAndClickButton('选择 视频A');
                } else if (key === 'w') {
                    handled = findAndClickButton('选择 视频B');
                } else if (key === 'd') {
                    handled = findAndClickButton('两者相当');
                }
                // 导航按钮
                else if (key === 'q') {
                    handled = findAndClickButton('⬅️ 上一题');
                } else if (key === 'e') {
                    handled = findAndClickButton('➡️ 下一题');
                }
                
                if (handled) {
                    e.preventDefault();
                    input.value = ''; // 清空输入
                }
            });
            
            // 清空输入内容
            input.addEventListener('input', function() {
                input.value = '';
            });
            
            console.log('Keyboard shortcuts ready: A=VideoA, W=VideoB, D=Tie, Q=Prev, E=Next');
        </script>
    </body>
    </html>
    """
    components.html(keyboard_listener_html, height=1, width=1)


def show_completion_page(judge_name):
    """显示完成页面"""
    st.balloons()
    st.success(f"🎉 恭喜 {judge_name}！")
    st.title("✅ 所有任务已完成！")
    st.markdown("""
    ### 感谢您的辛勤工作！
    
    您已经完成了所有分配的评测任务。
    
    如有新任务，系统会自动分配。请稍后刷新页面查看。
    """)
    
    if st.button("🔄 刷新页面"):
        st.rerun()


def main():
    """主函数"""
    # 获取URL参数
    params = st.query_params
    uid = params.get("uid", None)
    
    # 验证UID
    if not uid:
        st.error("❌ 缺少访问令牌（uid参数）")
        st.stop()
    
    judge_info = verify_judge(uid)
    if not judge_info:
        st.error("❌ 无效的访问令牌")
        st.stop()
    
    judge_id = judge_info['judge_id']
    judge_name = judge_info['judge_name']
    
    # 保存到session
    st.session_state.judge_id = judge_id
    st.session_state.judge_name = judge_name
    
    # 初始化历史导航索引
    if 'history_index' not in st.session_state:
        st.session_state.history_index = -1  # -1表示当前任务，0表示最近一次历史，1表示倒数第二次，...
    
    # 获取进度
    completed, total_assigned = get_progress(judge_id)
    completed_count = get_completed_count(judge_id)
    
    # 显示侧边栏
    show_sidebar(judge_name, completed, total_assigned)
    
    # 根据历史索引获取任务
    if st.session_state.history_index == -1:
        # 正常模式：获取当前未评任务
        task = get_current_task(judge_id)
        if task:
            show_task(task, is_review=False, history_index=-1, max_history=completed_count)
        else:
            show_completion_page(judge_name)
    else:
        # 历史模式：获取历史任务
        task = get_history_task(judge_id, st.session_state.history_index)
        if task:
            show_task(task, is_review=True, history_index=st.session_state.history_index, max_history=completed_count)
        else:
            st.warning("⚠️ 没有更多历史任务了")
            if st.button("返回当前任务"):
                st.session_state.history_index = -1
                st.rerun()


if __name__ == "__main__":
    main()

