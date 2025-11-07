#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控视频变化并动态更新数据库
- 定期扫描genvideo目录，检测新增视频，自动添加到评测任务中
- 检测已删除的视频，自动清理未完成的任务（保留已评测数据）
"""
import os
import re
import csv
import json
import time
import shutil
import sqlite3
import argparse
import socket
import sys
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 设置输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def sample_category(sample_id: str) -> str | None:
    """从sample_id提取类别"""
    m = re.match(r'^(.*)_(multi|single)_\d{3}$', sample_id)
    return m.group(1) if m else None


def read_prompt_text(sample_id: str, prompt_root: Path) -> str:
    """读取prompt文本"""
    cat = sample_category(sample_id)
    if not cat:
        return sample_id
    
    prompt_file = prompt_root / cat / f'{sample_id}.txt'
    if prompt_file.exists():
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[WARN] 无法读取prompt: {prompt_file}: {e}")
    return sample_id


def get_existing_data(db_path: str) -> dict:
    """获取数据库中已存在的数据"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 获取已存在的prompts
    cur.execute("SELECT id FROM prompts")
    existing_prompts = set(row[0] for row in cur.fetchall())
    
    # 获取已存在的videos (prompt_id, modelname)
    cur.execute("SELECT prompt_id, modelname FROM videos")
    existing_videos = set((row[0], row[1]) for row in cur.fetchall())
    
    # 获取所有模型
    cur.execute("SELECT DISTINCT modelname FROM videos WHERE modelname IS NOT NULL")
    existing_models = set(row[0] for row in cur.fetchall())
    
    # 获取所有video记录（用于删除检测）
    cur.execute("""
        SELECT v.id, v.prompt_id, v.modelname, v.sample_id
        FROM videos v
        WHERE v.modelname IS NOT NULL
    """)
    db_video_records = {}  # {video_id: (sample_id, modelname)}
    for video_id, prompt_id, modelname, sample_id in cur.fetchall():
        db_video_records[video_id] = (sample_id, modelname)
    
    conn.close()
    
    return {
        'prompts': existing_prompts,
        'videos': existing_videos,
        'models': existing_models,
        'video_records': db_video_records
    }


def scan_all_videos(gen_root: Path, ref_root: Path) -> dict:
    """扫描所有视频文件"""
    # 扫描参考视频
    ref_videos = {}
    for cat_dir in ref_root.iterdir():
        if not cat_dir.is_dir():
            continue
        inner_dir = cat_dir / cat_dir.name
        if not inner_dir.exists():
            inner_dir = cat_dir
        for p in inner_dir.glob('*.mp4'):
            ref_videos[p.stem] = p
    
    # 扫描生成视频
    gen_videos = defaultdict(dict)  # {sample_id: {model: path}}
    
    for model_dir in gen_root.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_name = model_dir.name
        inner_dir = model_dir / model_name
        if not inner_dir.exists():
            inner_dir = model_dir
        
        for p in inner_dir.glob('*.mp4'):
            sample_id = p.stem
            # 只保留有对应参考视频的
            if sample_id in ref_videos:
                gen_videos[sample_id][model_name] = p
    
    return {
        'ref_videos': ref_videos,
        'gen_videos': gen_videos
    }


def detect_new_content(scanned_data: dict, existing_data: dict) -> dict:
    """检测新增内容"""
    new_prompts = set()
    new_videos = []  # [(sample_id, model, path)]
    new_models = set()
    
    gen_videos = scanned_data['gen_videos']
    
    for sample_id, models in gen_videos.items():
        # 新的prompt（参考视频）
        if sample_id not in existing_data['prompts']:
            new_prompts.add(sample_id)
        
        # 新的视频或新的模型
        for model, path in models.items():
            if model not in existing_data['models']:
                new_models.add(model)
            
            if (sample_id, model) not in existing_data['videos']:
                new_videos.append((sample_id, model, path))
    
    return {
        'new_prompts': new_prompts,
        'new_videos': new_videos,
        'new_models': new_models
    }


def copy_to_static(sample_id: str, model: str, gen_path: Path, ref_path: Path, static_root: Path):
    """复制视频到静态服务目录"""
    # 生成视频
    gen_dir = static_root / 'gen' / sample_id
    gen_dir.mkdir(parents=True, exist_ok=True)
    gen_dst = gen_dir / f'{model}.mp4'
    if not gen_dst.exists() or os.path.getsize(gen_dst) == 0:
        shutil.copy2(gen_path, gen_dst)
    
    # 参考视频
    ref_dir = static_root / 'ref' / sample_id
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_dst = ref_dir / 'ref.mp4'
    if not ref_dst.exists() or os.path.getsize(ref_dst) == 0:
        if ref_path and ref_path.exists():
            shutil.copy2(ref_path, ref_dst)


def shuffle_pending_tasks_for_judge(conn, judge_id, seed=None):
    """随机打散单个judge的待评测任务
    
    Args:
        conn: 数据库连接
        judge_id: 评审员ID
        seed: 随机种子
    
    Returns:
        打散的任务数量
    """
    cur = conn.cursor()
    
    # 1. 获取已完成任务
    cur.execute("""
        SELECT id, display_order, task_id
        FROM assignments
        WHERE judge_id = ? AND finished = 1
        ORDER BY display_order
    """, (judge_id,))
    finished_assignments = cur.fetchall()
    
    # 2. 获取未完成任务
    cur.execute("""
        SELECT id, display_order, task_id
        FROM assignments
        WHERE judge_id = ? AND finished = 0
        ORDER BY display_order
    """, (judge_id,))
    pending_assignments = cur.fetchall()
    
    if not pending_assignments:
        return 0
    
    # 3. 找出最大的finished display_order
    if finished_assignments:
        max_finished_order = max(a[1] for a in finished_assignments)
    else:
        max_finished_order = -1
    
    # 4. 随机打散未完成任务
    if seed is None:
        seed = random.randint(1, 100000)
    rnd = random.Random(f"{seed}-judge-{judge_id}")
    pending_ids = [a[0] for a in pending_assignments]
    rnd.shuffle(pending_ids)
    
    # 5. 重新分配display_order
    updates = []
    for new_order, assign_id in enumerate(pending_ids, start=max_finished_order + 1):
        updates.append((new_order, assign_id))
    
    # 6. 批量更新数据库
    cur.executemany("""
        UPDATE assignments
        SET display_order = ?
        WHERE id = ?
    """, updates)
    
    return len(pending_assignments)


def update_database(db_path: str, new_content: dict, scanned_data: dict, 
                    prompt_root: Path, video_base: str, static_root: Path):
    """增量更新数据库"""
    if not new_content['new_prompts'] and not new_content['new_videos']:
        return 0, 0, 0
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    ref_videos = scanned_data['ref_videos']
    gen_videos = scanned_data['gen_videos']
    
    # 1. 添加新的prompts
    prompts_added = 0
    for sample_id in new_content['new_prompts']:
        ref_path = ref_videos.get(sample_id)
        if not ref_path:
            continue
        
        prompt_text = read_prompt_text(sample_id, prompt_root)
        ref_url = f"{video_base}/ref/{sample_id}/ref.mp4"
        
        cur.execute(
            "INSERT OR IGNORE INTO prompts (id, text, ref_path, sample_id) VALUES (?, ?, ?, ?)",
            (sample_id, prompt_text, ref_url, sample_id)
        )
        prompts_added += 1
        print(f"  [+] 新增prompt: {sample_id}")
    
    # 2. 添加新的videos
    videos_added = 0
    for sample_id, model, gen_path in new_content['new_videos']:
        # 获取该prompt下已有的视频数量，确定variant_index
        cur.execute("SELECT MAX(variant_index) FROM videos WHERE prompt_id = ?", (sample_id,))
        result = cur.fetchone()
        max_variant = result[0] if result[0] else 0
        variant_index = max_variant + 1
        
        gen_url = f"{video_base}/gen/{sample_id}/{model}.mp4"
        
        cur.execute(
            """INSERT INTO videos (prompt_id, variant_index, path, modelname, sample_id) 
               VALUES (?, ?, ?, ?, ?)""",
            (sample_id, variant_index, gen_url, model, sample_id)
        )
        videos_added += 1
        
        # 复制到静态目录
        ref_path = ref_videos.get(sample_id)
        copy_to_static(sample_id, model, gen_path, ref_path, static_root)
        
        print(f"  [+] 新增视频: {sample_id} / {model} (variant {variant_index})")
    
    conn.commit()
    
    # 3. 为新视频创建tasks和assignments（V2系统）
    tasks_added = 0
    assignments_added = 0
    
    if videos_added > 0:
        # 检查是否有tasks表（V2系统）
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        has_tasks_table = cur.fetchone() is not None
        
        # 获取所有评审员
        cur.execute("SELECT id FROM judges")
        judges = [row[0] for row in cur.fetchall()]
        
        if has_tasks_table:
            # V2系统：创建task，然后为所有judge创建assignment
            for sample_id, model, _ in new_content['new_videos']:
                # 获取video_id
                cur.execute(
                    "SELECT id FROM videos WHERE prompt_id = ? AND modelname = ?",
                    (sample_id, model)
                )
                result = cur.fetchone()
                if not result:
                    continue
                video_id = result[0]
                
                # 创建task（如果不存在）
                cur.execute("""
                    INSERT OR IGNORE INTO tasks (prompt_id, video_id, required_ratings, current_ratings, completed)
                    VALUES (?, ?, 3, 0, 0)
                """, (sample_id, video_id))
                
                # 获取task_id
                cur.execute("SELECT id FROM tasks WHERE video_id = ?", (video_id,))
                task_result = cur.fetchone()
                if not task_result:
                    continue
                task_id = task_result[0]
                tasks_added += 1
                
                # 为每个judge创建assignment（临时添加到末尾，稍后会重新打散）
                for judge_id in judges:
                    # 检查是否已存在
                    cur.execute("""
                        SELECT id FROM assignments 
                        WHERE judge_id = ? AND task_id = ?
                    """, (judge_id, task_id))
                    if cur.fetchone():
                        continue  # 已存在，跳过
                    
                    # 获取该judge的下一个display_order
                    cur.execute("""
                        SELECT COALESCE(MAX(display_order), -1) + 1
                        FROM assignments
                        WHERE judge_id = ?
                    """, (judge_id,))
                    next_order = cur.fetchone()[0]
                    
                    # 创建assignment
                    cur.execute("""
                        INSERT INTO assignments (judge_id, task_id, display_order, finished)
                        VALUES (?, ?, ?, 0)
                    """, (judge_id, task_id, next_order))
                    assignments_added += 1
            
            conn.commit()
            print(f"  [+] 创建 {tasks_added} 个tasks")
            print(f"  [+] 为 {len(judges)} 个评审员创建了 {assignments_added} 个assignments")
            
            # 4. 自动重新打散所有judge的未完成任务
            if assignments_added > 0:
                print(f"  [*] 正在重新打散所有评审员的待评测任务...")
                seed = random.randint(1, 100000)
                total_shuffled = 0
                for judge_id in judges:
                    shuffled = shuffle_pending_tasks_for_judge(conn, judge_id, seed)
                    total_shuffled += shuffled
                conn.commit()
                print(f"  [✓] 已重新打散 {total_shuffled} 个待评测任务（随机种子: {seed}）")
        else:
            # V1系统：旧的逻辑（兼容）
            for sample_id, model, _ in new_content['new_videos']:
                # 获取video_id
                cur.execute(
                    "SELECT id FROM videos WHERE prompt_id = ? AND modelname = ?",
                    (sample_id, model)
                )
                result = cur.fetchone()
                if not result:
                    continue
                video_id = result[0]
                
                # 为每个评审员创建任务
                for judge_id in judges:
                    # 检查是否已存在
                    cur.execute(
                        """SELECT id FROM assignments 
                           WHERE judge_id = ? AND prompt_id = ? AND order_json = ?""",
                        (judge_id, sample_id, json.dumps([video_id]))
                    )
                    if cur.fetchone():
                        continue
                    
                    cur.execute(
                        """INSERT INTO assignments (judge_id, prompt_id, order_json, finished) 
                           VALUES (?, ?, ?, 0)""",
                        (judge_id, sample_id, json.dumps([video_id]))
                    )
                    assignments_added += 1
            
            conn.commit()
            print(f"  [+] 为 {len(judges)} 个评审员创建了 {assignments_added} 个新任务")
    
    conn.close()
    
    return prompts_added, videos_added, assignments_added


def detect_deleted_videos(db_video_records: dict, scanned_data: dict) -> list:
    """检测已删除的视频
    
    Args:
        db_video_records: {video_id: (sample_id, modelname)}
        scanned_data: scan_all_videos()的返回结果
    
    Returns:
        [(video_id, sample_id, modelname), ...]
    """
    deleted_videos = []
    
    for video_id, (sample_id, modelname) in db_video_records.items():
        # 检查文件是否还存在
        if sample_id not in scanned_data['gen_videos']:
            # 该sample完全没有生成视频了
            deleted_videos.append((video_id, sample_id, modelname))
        elif modelname not in scanned_data['gen_videos'][sample_id]:
            # 该sample的这个model视频被删除了
            deleted_videos.append((video_id, sample_id, modelname))
    
    return deleted_videos


def cleanup_deleted_videos(db_path: str, deleted_videos: list) -> dict:
    """自动清理已删除视频的相关记录（软删除模式）
    
    软删除策略：
    - 保留所有已完成的评分（ratings）
    - 删除未完成的任务（assignments where finished=0）
    - 删除未评测的视频记录（videos without ratings）
    
    Returns:
        {'videos': int, 'assignments': int, 'ratings_kept': int}
    """
    if not deleted_videos:
        return {'videos': 0, 'assignments': 0, 'ratings_kept': 0}
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    video_ids = [v[0] for v in deleted_videos]
    video_ids_str = ','.join(str(v) for v in video_ids)
    
    # 1. 检查有多少已有评分（需要保留）
    cur.execute(f"""
        SELECT COUNT(*) FROM ratings WHERE video_id IN ({video_ids_str})
    """)
    ratings_kept = cur.fetchone()[0]
    
    # 2. 获取有评分的video_ids（需要保留）
    cur.execute(f"""
        SELECT DISTINCT video_id FROM ratings WHERE video_id IN ({video_ids_str})
    """)
    videos_with_ratings = set(row[0] for row in cur.fetchall())
    
    # 3. 删除未完成的任务
    # 检查是否有tasks表（V2系统）
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    has_tasks_table = cur.fetchone() is not None
    
    assignments_deleted = 0
    tasks_deleted = 0
    
    if has_tasks_table:
        # V2系统：删除tasks（CASCADE会自动删除related assignments）
        print(f"       [清理] 删除未完成的tasks...", flush=True)
        cur.execute(f"""
            DELETE FROM tasks
            WHERE video_id IN ({video_ids_str})
            AND completed = 0
        """)
        tasks_deleted = cur.rowcount
        assignments_deleted = tasks_deleted * 10  # 估算
        print(f"       [清理] 删除了 {tasks_deleted} 个tasks", flush=True)
    else:
        # V1系统：检查每个assignment的order_json
        assignments_to_delete = []
        try:
            cur.execute("SELECT id, order_json FROM assignments WHERE finished = 0")
            for aid, order_json in cur.fetchall():
                try:
                    video_list = json.loads(order_json)
                    # 检查是否包含已删除的video_id
                    if any(vid in video_ids for vid in video_list):
                        assignments_to_delete.append(aid)
                except:
                    pass
            
            if assignments_to_delete:
                assignments_to_delete_str = ','.join(str(a) for a in assignments_to_delete)
                cur.execute(f"DELETE FROM assignments WHERE id IN ({assignments_to_delete_str})")
                assignments_deleted = cur.rowcount
        except sqlite3.OperationalError:
            # 如果order_json不存在，说明数据库结构不一致，跳过
            print("  [WARN] V1数据库结构不匹配，跳过assignments清理")
            pass
    
    # 4. 删除未评测的视频记录
    print(f"       [清理] 删除未评测的视频记录...", flush=True)
    videos_to_delete = [v for v in video_ids if v not in videos_with_ratings]
    print(f"       [清理] 找到 {len(videos_to_delete)} 个未评测视频需要删除", flush=True)
    
    videos_deleted = 0
    if videos_to_delete:
        print(f"       [清理] 正在执行DELETE操作（可能需要几秒钟）...", flush=True)
        videos_to_delete_str = ','.join(str(v) for v in videos_to_delete)
        cur.execute(f"DELETE FROM videos WHERE id IN ({videos_to_delete_str})")
        videos_deleted = cur.rowcount
        print(f"       [清理] DELETE操作完成，删除了 {videos_deleted} 条记录", flush=True)
    
    print(f"       [清理] 提交事务...", flush=True)
    conn.commit()
    print(f"       [清理] 事务提交完成", flush=True)
    conn.close()
    
    return {
        'videos': videos_deleted,
        'assignments': assignments_deleted,
        'tasks': tasks_deleted,
        'ratings_kept': ratings_kept
    }


def monitor_loop(args):
    """监控循环"""
    print("=" * 70)
    print("  视频监控服务已启动")
    print("=" * 70)
    print(f"\n监控目录: {args.gen_root}")
    print(f"数据库: {args.db}")
    print(f"扫描间隔: {args.interval} 秒")
    print(f"监控功能:")
    print(f"  - 自动检测并添加新视频")
    print(f"  - 自动检测并清理已删除视频的未完成任务")
    print(f"  - 保留所有已评测的数据")
    print(f"\n按 Ctrl+C 停止监控\n")
    
    gen_root = Path(args.gen_root)
    ref_root = Path(args.ref_root)
    prompt_root = Path(args.prompt_root)
    static_root = Path(args.static_root)
    
    local_ip = get_local_ip()
    video_base = f'http://{local_ip}:8010'
    
    scan_count = 0
    total_stats = {
        'prompts_added': 0,
        'videos_added': 0,
        'assignments_added': 0,
        'videos_deleted': 0,
        'assignments_deleted': 0,
        'ratings_kept': 0
    }
    
    print("✅ 监控服务已启动，准备开始第一次扫描...")
    print()
    
    try:
        while True:
            scan_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            print("=" * 70, flush=True)
            print(f"[{timestamp}] 开始扫描 #{scan_count}", flush=True)
            print("=" * 70, flush=True)
            
            # 1. 获取数据库现有数据
            print("  [1/4] 读取数据库...", flush=True)
            existing_data = get_existing_data(args.db)
            
            # 2. 扫描所有视频
            print("  [2/4] 扫描视频文件（可能需要几秒钟）...", flush=True)
            scanned_data = scan_all_videos(gen_root, ref_root)
            print(f"       找到 {len(scanned_data['gen_videos'])} 个样本的生成视频", flush=True)
            
            has_changes = False
            
            # 3. 检测新增内容
            print("  [3/4] 检测新增内容...", flush=True)
            new_content = detect_new_content(scanned_data, existing_data)
            
            # 4. 如果有新内容，更新数据库
            if new_content['new_prompts'] or new_content['new_videos']:
                has_changes = True
                print(f"\n  ✅ 发现新内容:")
                if new_content['new_prompts']:
                    print(f"     新参考视频: {len(new_content['new_prompts'])} 个")
                if new_content['new_videos']:
                    print(f"     新生成视频: {len(new_content['new_videos'])} 个")
                if new_content['new_models']:
                    print(f"     新模型: {', '.join(new_content['new_models'])}")
                
                prompts_added, videos_added, assignments_added = update_database(
                    args.db, new_content, scanned_data, prompt_root, video_base, static_root
                )
                
                total_stats['prompts_added'] += prompts_added
                total_stats['videos_added'] += videos_added
                total_stats['assignments_added'] += assignments_added
                
                print(f"     → 新增任务: {assignments_added} 个")
            
            # 5. 检测已删除的视频
            print("  [4/4] 检测已删除视频...", flush=True)
            deleted_videos = detect_deleted_videos(existing_data['video_records'], scanned_data)
            print(f"       检测完成，发现 {len(deleted_videos)} 个已删除视频", flush=True)
            
            # 6. 清理已删除视频的相关记录
            if deleted_videos:
                has_changes = True
                print(f"\n  🗑️  发现已删除视频: {len(deleted_videos)} 个", flush=True)
                print(f"       正在清理数据...", flush=True)
                
                # 按模型分组显示
                by_model = defaultdict(int)
                for _, sample_id, modelname in deleted_videos:
                    by_model[modelname] += 1
                
                for model, count in sorted(by_model.items()):
                    print(f"     {model}: {count} 个")
                
                cleanup_result = cleanup_deleted_videos(args.db, deleted_videos)
                
                total_stats['videos_deleted'] += cleanup_result['videos']
                total_stats['assignments_deleted'] += cleanup_result['assignments']
                total_stats['ratings_kept'] += cleanup_result['ratings_kept']
                
                print(f"     → 删除未完成任务: {cleanup_result['assignments']} 个")
                print(f"     → 删除未评测视频: {cleanup_result['videos']} 个")
                if cleanup_result['ratings_kept'] > 0:
                    print(f"     → 保留已评测数据: {cleanup_result['ratings_kept']} 个 ✓")
            
            # 7. 显示状态
            scan_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if has_changes:
                print(f"\n  📊 本次扫描统计:")
                print(f"     新增任务: {assignments_added if new_content['new_prompts'] or new_content['new_videos'] else 0}")
                print(f"     删除任务: {cleanup_result['assignments'] if deleted_videos else 0}")
                print(f"     评审员刷新页面后将看到更新")
            else:
                print("  ✓ 无变化")
            
            print(f"\n[{scan_end_time}] 扫描完成，等待 {args.interval} 秒后进行下一次扫描...\n")
            
            # 等待下一次扫描
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n\n监控服务已停止")
        print("=" * 70)
        print("  累计统计:")
        print(f"    新增prompts: {total_stats['prompts_added']}")
        print(f"    新增videos: {total_stats['videos_added']}")
        print(f"    新增assignments: {total_stats['assignments_added']}")
        print(f"    删除videos: {total_stats['videos_deleted']}")
        print(f"    删除assignments: {total_stats['assignments_deleted']}")
        print(f"    保留已评测数据: {total_stats['ratings_kept']}")
        print("=" * 70)


def main():
    ap = argparse.ArgumentParser(description='监控新增视频并动态更新数据库')
    project_root = Path(__file__).parent.parent
    
    ap.add_argument('--db', default='aiv_eval_v4.db', help='数据库路径')
    ap.add_argument('--gen-root', default=str(project_root / 'video' / 'genvideo'), 
                   help='生成视频根目录')
    ap.add_argument('--ref-root', default=str(project_root / 'video' / 'refvideo'), 
                   help='参考视频根目录')
    ap.add_argument('--prompt-root', default=str(project_root / 'prompt'), 
                   help='prompt文本根目录')
    ap.add_argument('--static-root', default=str(project_root / 'video' / 'human_eval_v4'), 
                   help='静态服务根目录')
    ap.add_argument('--interval', type=int, default=300, 
                   help='扫描间隔（秒），默认300秒=5分钟')
    ap.add_argument('--once', action='store_true', 
                   help='只运行一次，不持续监控')
    
    args = ap.parse_args()
    
    # 检查数据库是否存在
    if not os.path.exists(args.db):
        print(f"[ERROR] 数据库不存在: {args.db}")
        print("请先运行 setup_project.py 初始化数据库")
        return 1
    
    if args.once:
        # 单次运行模式
        print("=" * 70)
        print("  单次扫描模式")
        print("=" * 70)
        print("")
        
        existing_data = get_existing_data(args.db)
        scanned_data = scan_all_videos(Path(args.gen_root), Path(args.ref_root))
        
        # 检测新增
        new_content = detect_new_content(scanned_data, existing_data)
        
        # 检测删除
        deleted_videos = detect_deleted_videos(existing_data['video_records'], scanned_data)
        
        has_changes = False
        
        # 处理新增
        if new_content['new_prompts'] or new_content['new_videos']:
            has_changes = True
            print("✅ 发现新内容:")
            if new_content['new_prompts']:
                print(f"   新参考视频: {len(new_content['new_prompts'])} 个")
            if new_content['new_videos']:
                print(f"   新生成视频: {len(new_content['new_videos'])} 个")
            if new_content['new_models']:
                print(f"   新模型: {', '.join(new_content['new_models'])}")
            
            print("\n正在更新数据库...")
            prompts_added, videos_added, assignments_added = update_database(
                args.db, new_content, scanned_data, Path(args.prompt_root), 
                f'http://{get_local_ip()}:8010', Path(args.static_root)
            )
            print(f"   新增prompts: {prompts_added}")
            print(f"   新增videos: {videos_added}")
            print(f"   新增assignments: {assignments_added}\n")
        
        # 处理删除
        if deleted_videos:
            has_changes = True
            print(f"🗑️  发现已删除视频: {len(deleted_videos)} 个")
            
            by_model = defaultdict(int)
            for _, sample_id, modelname in deleted_videos:
                by_model[modelname] += 1
            
            for model, count in sorted(by_model.items()):
                print(f"   {model}: {count} 个")
            
            print("\n正在清理数据库...")
            cleanup_result = cleanup_deleted_videos(args.db, deleted_videos)
            print(f"   删除未完成任务: {cleanup_result['assignments']}")
            print(f"   删除未评测视频: {cleanup_result['videos']}")
            if cleanup_result['ratings_kept'] > 0:
                print(f"   保留已评测数据: {cleanup_result['ratings_kept']} ✓\n")
        
        if not has_changes:
            print("✓ 无变化\n")
        
        print("=" * 70)
    else:
        # 持续监控模式
        monitor_loop(args)


if __name__ == '__main__':
    main()

