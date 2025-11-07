import os, json, sqlite3, time
import csv
from functools import lru_cache
from pathlib import Path
import streamlit as st
from streamlit.components.v1 import html as embed_html
import random

_env_db = os.getenv('AIV_DB')
if _env_db and _env_db.strip():
    DB_PATH = _env_db
else:
    # Prefer round2 DB if present, otherwise fall back to original
    DB_PATH = 'aiv_eval_v4_round2.db' if os.path.exists('aiv_eval_v4_round2.db') else 'aiv_eval_v4.db'
# Blind review by default: hide model names and auto-scores unless explicitly enabled
SHOW_MODEL = os.getenv('AIV_SHOW_MODEL', '0') == '1'
SHOW_AUTO = os.getenv('AIV_SHOW_AUTO', '0') == '1'
ORDER_SEED = int(os.getenv('AIV_SEED', '42'))
st.set_page_config(page_title="AIV Eval v4", layout="wide")

INTRO = (
    "请先观看左侧参考视频，再观看右侧生成视频，然后在四个维度（1–5）打分。"
    "每个任务只需评测一个参考视频-生成视频对。"
)

RULES_SUMMARY = "四维评分：基本语义对齐、运动、事件时序一致性、世界知识与功能性真实度（1–5 分）。"

# 读取详细评分规则
def load_detailed_rules():
    """从rule.txt加载详细评分规则"""
    rule_file = Path('rule.txt')
    if rule_file.exists():
        try:
            with open(rule_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"加载规则文件失败：{e}"
    return "未找到规则文件（rule.txt）"

# 数据路径配置：支持小规模和大规模数据切换
import sys
from pathlib import Path as _Path
_project_root = _Path(__file__).parent.parent

# 使用环境变量控制数据规模，默认使用大规模数据
import os as _os
_use_large_scale = _os.getenv('AIV_DATA_SCALE', 'large') == 'large'

if _use_large_scale:
    # 大规模数据（上千个样本，5个模型）
    _data_root = _project_root / 'video'
    DATA_ROOT = _data_root
    PROMPT_ROOT = _project_root / 'prompt'
    AUTO_SCORE_CSV = _data_root / 'eval_result' / 'combined_scores.csv'  # 如果没有可以不用
    MODEL_DIRS = [
        ('wan21', _data_root / 'genvideo' / 'wan21'),
        ('vidu', _data_root / 'genvideo' / 'vidu'),
        ('cogfun', _data_root / 'genvideo' / 'cogfun'),
        ('cogvideo5b', _data_root / 'genvideo' / 'cogvideo5b'),
        ('videocrafter', _data_root / 'genvideo' / 'videocrafter'),
    ]
else:
    # 小规模数据（104个样本，7个模型）- 用于测试
    _small_root = _project_root / 'small'
    DATA_ROOT = _small_root
    PROMPT_ROOT = _small_root / 'prompts'
    AUTO_SCORE_CSV = _small_root / 'eval_result' / 'combined_scores.csv'
    MODEL_DIRS = [
        ('cogfun', _small_root / 'genvideo' / 'cogfun'),
        ('cogvideo_5b', _small_root / 'genvideo' / 'cogvideo_5b'),
        ('videocrafter', _small_root / 'genvideo' / 'videocrafter'),
        ('wan21', _small_root / 'genvideo' / 'wan21'),
        ('kling', _small_root / 'genvideo' / 'kling'),
        ('jimeng', _small_root / 'genvideo' / 'jimeng'),
        ('opensora', _small_root / 'genvideo' / 'opensora'),
    ]
MODEL_ALIASES = {
    'cogfun': 'cogfun',
    'cogvideo_5b': 'cogvideo_5b',
    'cogvideo5b': 'cogvideo_5b',
    'videocrafter': 'videocrafter',
    'crafter': 'videocrafter',
    'sora': 'sora',
    'wan21': 'wan21',
    'kling': 'kling',
    'jimeng': 'jimeng',
    'opensora': 'opensora',
}


@lru_cache(maxsize=1)
def prompt_index() -> dict:
    mapping: dict[str, str] = {}
    if PROMPT_ROOT.exists():
        files = sorted(PROMPT_ROOT.rglob('*.json'))
        for idx, file in enumerate(files, 1):
            mapping[str(idx)] = file.stem
    return mapping




@lru_cache(maxsize=1)
def auto_score_lookup() -> dict:
    lookup: dict[tuple[str, str], dict[str, float | None]] = {}
    if not AUTO_SCORE_CSV.exists():
        return lookup
    with AUTO_SCORE_CSV.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row.get('modelname')
            clip_id = row.get('ID')
            if not model or not clip_id:
                continue
            canonical = MODEL_ALIASES.get(model, model)

            def safe_float(val):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None

            entry = lookup.setdefault(
                (canonical, clip_id),
                {'semantic': None, 'temporal': None, 'motion': None, 'world': None}
            )
            for src_key, dst_key in (('S_base', 'semantic'), ('S_event', 'temporal'), ('S_motion', 'motion'), ('S_world', 'world')):
                value = safe_float(row.get(src_key))
                if value is not None:
                    entry[dst_key] = value
    return lookup


@lru_cache(maxsize=None)
def model_sequence_for(prompt_key: str | None) -> list[str]:
    seq: list[str] = []
    if not prompt_key:
        return seq
    for name, directory in MODEL_DIRS:
        if (directory / f"{prompt_key}.mp4").exists():
            seq.append(name)
    return seq


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def qp(name, default=None):
    if hasattr(st, 'query_params'):
        q = st.query_params
        v = q.get(name, default)
    else:
        q = st.experimental_get_query_params()
        raw = q.get(name)
        v = raw[0] if isinstance(raw, list) and raw else raw
        if v is None:
            v = default
    return v


def judge_by_token(conn, t):
    cur = conn.cursor()
    cur.execute('SELECT id,name FROM judges WHERE token=?', (t,))
    return cur.fetchone()


def progress(conn, j):
    """获取评审员的进度（基于assignments）"""
    cur = conn.cursor()
    
    # 获取该judge已完成的assignments数量
    cur.execute('SELECT COUNT(*) FROM assignments WHERE judge_id=? AND finished=1', (j,))
    done = cur.fetchone()[0]
    
    # 获取该judge待做的assignments数量（task还未完成的）
    cur.execute('''
        SELECT COUNT(*) 
        FROM assignments a
        JOIN tasks t ON a.task_id = t.id
        WHERE a.judge_id = ? AND a.finished = 0 AND t.completed = 0
    ''', (j,))
    pending = cur.fetchone()[0]
    
    total = done + pending
    
    return done, total


def next_assign(conn, j):
    """获取下一个未完成的任务（一个视频对）
    
    关键：按display_order排序，确保每个judge看到的任务顺序不同
    只显示task还未被评3次的任务
    
    特殊情况：如果用户有rating但finished=0（正在编辑），即使task.completed=1也允许继续
    这样用户可以继续调整评分，不会因为其他人完成3次评分而被跳过
    """
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT a.id, a.task_id, t.prompt_id, t.video_id, p.text, p.ref_path
          FROM assignments a 
          JOIN tasks t ON a.task_id = t.id
          JOIN prompts p ON t.prompt_id = p.id
         WHERE a.judge_id = ? 
           AND a.finished = 0
           AND (t.completed = 0 OR EXISTS (
             SELECT 1 FROM ratings 
             WHERE ratings.judge_id = a.judge_id 
             AND ratings.video_id = t.video_id
           ))
         ORDER BY a.display_order
         LIMIT 1
        ''',
        (j,)
    )
    return cur.fetchone()


def previous_assign(conn, j, current_assign_id):
    """获取上一个已完成的任务ID
    
    关键：按display_order排序查找上一个任务，因为任务已被随机打散
    """
    cur = conn.cursor()
    
    # 首先获取当前任务的display_order
    cur.execute(
        'SELECT display_order FROM assignments WHERE id = ?',
        (current_assign_id,)
    )
    current_row = cur.fetchone()
    if not current_row:
        return None
    current_order = current_row[0]
    
    # 查找display_order小于当前任务的最近一个已完成任务
    cur.execute(
        '''
        SELECT id FROM assignments
         WHERE judge_id=? AND display_order < ? AND finished=1
         ORDER BY display_order DESC LIMIT 1
        ''',
        (j, current_order)
    )
    row = cur.fetchone()
    return row[0] if row else None

def vids_by_ids(conn, ids, prompt_key):
    if not ids:
        return []
    placeholders = ','.join(['?'] * len(ids))
    cur = conn.cursor()
    cur.execute(f'SELECT id,variant_index,path FROM videos WHERE id IN ({placeholders})', ids)
    rows = cur.fetchall()
    mp = {r[0]: {'video_id': r[0], 'variant': r[1], 'path': r[2]} for r in rows}
    # Some ids may be stale if assignments were created before videos changed.
    # Only keep those that still exist to avoid KeyError.
    ordered = [mp[i] for i in ids if i in mp]
    model_seq = model_sequence_for(prompt_key)
    auto_lookup = auto_score_lookup()
    for item in ordered:
        idx = item['variant'] - 1
        model_name = model_seq[idx] if idx < len(model_seq) else None
        item['model_name'] = model_name if SHOW_MODEL else None
        item['auto_scores'] = (
            auto_lookup.get((model_name, prompt_key)) if (SHOW_AUTO and model_name and prompt_key) else None
        )
    return ordered


def get_video_info(conn, video_id: int) -> dict | None:
    """获取单个视频的信息"""
    cur = conn.cursor()
    cur.execute('SELECT id, path, modelname, variant_index, prompt_id FROM videos WHERE id=?', (video_id,))
    row = cur.fetchone()
    if not row:
        return None
    
    return {
        'video_id': row[0],
        'path': row[1],
        'model_name': (row[2] if SHOW_MODEL else row[2]),  # 总是获取模型名用于内部处理
        'variant': row[3],
        'prompt_id': row[4]
    }


def existing(conn, j, v):
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT score_semantic,score_motion,score_temporal,score_realism
          FROM ratings WHERE judge_id=? AND video_id=?
        ''',
        (j, v)
    )
    row = cur.fetchone()
    return {'semantic': row[0], 'motion': row[1], 'temporal': row[2], 'realism': row[3]} if row else None


def save(conn, j, v, sc):
    # Persist 4 scores plus modelname/sample_id/prompt_id for richer analysis
    cur = conn.cursor()
    cur.execute('SELECT modelname, sample_id, prompt_id FROM videos WHERE id=?', (v,))
    row = cur.fetchone()
    model = row[0] if row else None
    sample = row[1] if row else None
    prompt = row[2] if row else None
    conn.execute(
        '''
        INSERT INTO ratings(judge_id,prompt_id,video_id,score_semantic,score_motion,score_temporal,score_realism,modelname,sample_id)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(judge_id,video_id) DO UPDATE SET
          score_semantic=excluded.score_semantic,
          score_motion=excluded.score_motion,
          score_temporal=excluded.score_temporal,
          score_realism=excluded.score_realism,
          modelname=excluded.modelname,
          sample_id=excluded.sample_id,
          prompt_id=excluded.prompt_id
        ''',
        (j, prompt, v, sc['semantic'], sc['motion'], sc['temporal'], sc['realism'], model, sample)
    )
    conn.commit()


def mark_done(conn, assign_id):
    """标记任务完成（通过assignment ID）
    
    注意：
    1. 更新assignment.finished=1和finished_at
    2. 更新对应rating的submitted_at（如果存在）
    3. 数据库触发器会自动更新task的current_ratings和completed状态
    """
    # 获取assignment的信息
    cur = conn.cursor()
    cur.execute('''
        SELECT a.judge_id, t.video_id
        FROM assignments a
        JOIN tasks t ON a.task_id = t.id
        WHERE a.id = ?
    ''', (assign_id,))
    result = cur.fetchone()
    
    if result:
        judge_id, video_id = result
        
        # 更新assignment
        conn.execute(
            'UPDATE assignments SET finished=1, finished_at=CURRENT_TIMESTAMP WHERE id=?', 
            (assign_id,)
        )
        
        # 更新rating的submitted_at
        conn.execute('''
            UPDATE ratings 
            SET submitted_at=CURRENT_TIMESTAMP 
            WHERE judge_id=? AND video_id=? AND submitted_at IS NULL
        ''', (judge_id, video_id))
        
        conn.commit()


def mark_undone(conn, assign_id):
    """取消任务完成标记（用于返回上一题）
    
    注意：
    1. 保留rating记录，用户可以看到并修改之前的评分
    2. 清除submitted_at，表示未正式提交
    3. finished=0表示"未确认完成"，是一个临时状态
    """
    # 获取assignment的信息
    cur = conn.cursor()
    cur.execute('''
        SELECT a.judge_id, t.video_id
        FROM assignments a
        JOIN tasks t ON a.task_id = t.id
        WHERE a.id = ?
    ''', (assign_id,))
    result = cur.fetchone()
    
    if result:
        judge_id, video_id = result
        
        # 将assignment标记为未完成
        conn.execute('''
            UPDATE assignments
            SET finished = 0, finished_at = NULL
            WHERE id = ?
        ''', (assign_id,))
        
        # 清除rating的submitted_at
        conn.execute('''
            UPDATE ratings
            SET submitted_at = NULL
            WHERE judge_id = ? AND video_id = ?
        ''', (judge_id, video_id))
        
        conn.commit()


def min_guard(start_ts, minimum=0):
    if start_ts is None:
        return 0, False
    elapsed = int(time.time() - start_ts)
    remain = max(0, minimum - elapsed)
    return remain, elapsed >= minimum


def vbox(ref_src, gen_src, height=520):
    html = """
    <style>
      .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: start; }}
      .panel {{ display:flex; flex-direction:column; gap:12px; }}
      video.ev {{ width:100%; height:{h}px; object-fit:contain; background:#000; border-radius:12px; }}
      .caption {{ font:600 14px/1.4 ui-sans-serif,system-ui; color:#222 }}
    </style>
    <div class="grid">
      <div class="panel">
        <video id="refV" class="ev" src="{ref}" controls autoplay muted playsinline></video>
        <div class="caption">参考视频</div>
      </div>
      <div class="panel">
        <video id="genV" class="ev" src="{gen}" controls autoplay muted playsinline></video>
        <div class="caption">生成视频</div>
      </div>
    </div>
    <script>
      const refV = document.getElementById('refV');
      const genV = document.getElementById('genV');
      function syncPlay(){{ try{{ refV.currentTime=0; genV.currentTime=0; refV.play(); genV.play(); }}catch(e){{}} }}
      window.addEventListener('load', syncPlay);
      document.addEventListener('DOMContentLoaded', syncPlay);
    </script>
    """.format(ref=ref_src, gen=gen_src, h=height)
    embed_html(html, height=height + 120, scrolling=False)


def get_video_url(sample_id: str, model: str = None, is_ref: bool = False) -> str:
    """根据sample_id和model生成视频URL（用于评分示例展示）"""
    # 使用与当前评测相同的视频服务器
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    base_url = f"http://{local_ip}:8010"
    
    if is_ref:
        return f"{base_url}/ref/{sample_id}/ref.mp4"
    else:
        return f"{base_url}/gen/{sample_id}/{model}.mp4"


def show_scoring_guide():
    """展示详细的评分规则"""
    st.title("📋 AI视频评分规则完整指南")
    
    # 返回主页按钮
    if st.button("⬅ 返回评测", type="primary", use_container_width=True):
        st.session_state.page = "main"
        st.rerun()
    
    st.markdown("---")
    
    # 加载并显示详细规则
    rules_content = load_detailed_rules()
    
    # 使用容器展示规则，提供更好的可读性
    with st.container():
        # 将规则文本按行处理，优化格式
        lines = rules_content.split('\n')
        formatted_text = []
        
        for line in lines:
            # 检测标题行（纯中文开头且较短）
            if line and not line[0].isspace():
                # 一级标题（如"一.总览"）
                if line.startswith(('一', '二', '三', '四', '五', '六', '七', '八', '九', '十')):
                    formatted_text.append(f"\n## {line}\n")
                # 数字标题（如"1.基础语义对齐"）
                elif line[0].isdigit() and '.' in line[:3]:
                    formatted_text.append(f"\n### {line}\n")
                # 带括号的子标题（如"1）要点"）
                elif line[:2].replace('）', ')').replace('（', '(').count(')') > 0:
                    formatted_text.append(f"\n**{line}**\n")
                else:
                    formatted_text.append(line)
            else:
                formatted_text.append(line)
        
        formatted_rules = '\n'.join(formatted_text)
        
        # 显示格式化后的规则
        st.markdown(formatted_rules)
    
    st.markdown("---")
    
    # 底部提示
    st.info("💡 **提示**：请仔细阅读评分规则，确保评分标准一致。如有疑问，请联系项目负责人。")


def main_evaluation():
    """主评测页面"""
    st.title("🎬 AIV 视频主观评测")
    st.write(INTRO)
    if os.getenv('AIV_DEBUG','0') == '1':
        st.caption(f"[DEBUG] DB_PATH={DB_PATH}")
    
    # 修改规则按钮，点击后跳转到规则展示页面
    if st.button("📖 点击查看详细评分规则", type="secondary", use_container_width=True):
        st.session_state.page = "guide"
        st.rerun()

    token = qp('uid')
    if not token:
        st.error("缺少评审身份 token：请使用 /?uid=<token> 的链接进入。")
        st.stop()

    conn = get_conn()
    j = judge_by_token(conn, token)
    if not j:
        st.error("无效的 token。")
        st.stop()
    jid, jname = j

    st.info(f"当前评审：**{jname}**")
    done, total = progress(conn, jid)
    # 确保进度值在[0.0, 1.0]范围内
    progress_value = min(done / total, 1.0) if total > 0 else 0.0
    st.progress(progress_value, text=f"进度：{done}/{total}")

    # 获取下一个任务（现在是一个视频对）
    nxt = next_assign(conn, jid)
    if not nxt:
        st.success("🎉 已完成所有题目，感谢参与！")
        st.stop()

    # 解包新的返回值：assign_id, task_id, prompt_id, video_id, prompt_text, ref_video_path
    assign_id, task_id, pid, video_id, prompt_text, ref_path = nxt
    
    # 获取视频信息
    cur_vid = get_video_info(conn, video_id)
    if not cur_vid:
        st.error("当前视频不存在，请联系管理员。")
        st.stop()

    # 计时器（基于 assignment ID）
    timer_key = f"timer_{assign_id}"
    if timer_key not in st.session_state:
        st.session_state[timer_key] = time.time()

    # 返回上一题按钮
    prev_assign_id = previous_assign(conn, jid, assign_id)
    if prev_assign_id:
        if st.button("⬅ 返回上一题", key=f"back_{assign_id}", use_container_width=True):
            mark_undone(conn, prev_assign_id)
            # 清理上一题的session state，让它重新从数据库读取
            # 注意：保留了rating记录，所以会读取到用户之前的评分
            st.session_state.pop(f'timer_{prev_assign_id}', None)
            st.session_state.pop(f'scores_init_{prev_assign_id}', None)
            st.rerun()

    st.markdown("---")

    # 显示视频对
    vbox(ref_path, cur_vid['path'], height=520)
    st.markdown(f"**样本ID：** {pid}")
    st.markdown(f"**Prompt：** {prompt_text}")
    
    # 显示模型名（如果允许）
    model_name = cur_vid.get('model_name')
    if SHOW_MODEL and model_name:
        st.caption(f"**生成模型：** {model_name}")

    st.markdown("---")
    st.markdown("### 📊 请对生成视频进行四维评分")

    # 获取已有评分（如果有），只在第一次加载时从数据库读取
    # 之后使用session_state中的值，避免滑块跳回
    score_init_key = f"scores_init_{assign_id}"
    if score_init_key not in st.session_state:
        ex = existing(conn, jid, video_id) or {}
        st.session_state[score_init_key] = {
            'semantic': ex.get('semantic', 3),
            'motion': ex.get('motion', 3),
            'temporal': ex.get('temporal', 3),
            'realism': ex.get('realism', 3)
        }
    
    # 评分滑块 - 使用session_state作为初始值
    c1, c2 = st.columns(2)
    with c1:
        s_sem = st.slider(
            "**基本语义对齐**", 
            1, 5, 
            value=st.session_state[score_init_key]['semantic'], 
            key=f"sem_{assign_id}",
            help="核心语义是否表达准确；是否出现重大偏差"
        )
        s_mot = st.slider(
            "**运动**", 
            1, 5, 
            value=st.session_state[score_init_key]['motion'], 
            key=f"mot_{assign_id}",
            help="运动是否自然、连贯，无明显卡顿与伪影"
        )
    with c2:
        s_tem = st.slider(
            "**事件时序一致性**", 
            1, 5, 
            value=st.session_state[score_init_key]['temporal'], 
            key=f"tem_{assign_id}",
            help="事件顺序是否正确、节奏是否合理"
        )
        s_rea = st.slider(
            "**世界知识与功能性真实度**", 
            1, 5, 
            value=st.session_state[score_init_key]['realism'], 
            key=f"rea_{assign_id}",
            help="是否符合常识/物理规律、交互是否可信"
        )
    
    # 更新session_state中的值（保持最新）
    st.session_state[score_init_key]['semantic'] = s_sem
    st.session_state[score_init_key]['motion'] = s_mot
    st.session_state[score_init_key]['temporal'] = s_tem
    st.session_state[score_init_key]['realism'] = s_rea

    st.markdown("---")
    
    # 时间限制检查（可选，这里设为0表示无时间限制）
    remain, ok = min_guard(st.session_state[timer_key], 0)
    if not ok:
        st.warning(f"⏱️ 请再等 **{remain} 秒** 后再提交。")
    
    # 提示信息
    st.info("💡 提示：请完成评分后点击下方\"提交\"按钮，评分将在提交时保存到数据库")
    
    # 提交按钮
    if st.button("✅ 提交本题并进入下一题", disabled=not ok, use_container_width=True, type="primary"):
        try:
            # 保存评分到数据库
            save(conn, jid, video_id, dict(semantic=s_sem, motion=s_mot, temporal=s_tem, realism=s_rea))
            # 标记任务完成
            mark_done(conn, assign_id)
            # 清理当前任务的session state
            st.session_state.pop(timer_key, None)
            st.session_state.pop(score_init_key, None)
            st.success("✅ 已提交并保存，正在加载下一题…")
            time.sleep(0.5)  # 短暂延迟，让用户看到成功消息
            st.rerun()
        except Exception as e:
            st.error(f"❌ 提交失败：{e}")


def main():
    """主入口函数，根据session_state切换页面"""
    # 初始化页面状态
    if 'page' not in st.session_state:
        st.session_state.page = "main"
    
    # 页面路由
    if st.session_state.page == "guide":
        show_scoring_guide()
    else:
        main_evaluation()


if __name__ == '__main__':
    main()

