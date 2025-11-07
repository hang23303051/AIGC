#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Video Monitor - 简化的视频监控服务
核心功能：
1. 监控 video/genvideo 目录的新增视频
2. 检测新模型文件夹
3. 为新视频创建任务并分配给judges
4. 自动复制视频到视频服务器目录
"""
import sqlite3
import time
import random
import shutil
from pathlib import Path
from datetime import datetime
import argparse
import sys

def get_local_ip():
    """获取本机IP"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def scan_genvideo_directory(genvideo_root: Path) -> dict:
    """
    扫描genvideo目录，返回所有找到的视频
    
    支持两种目录结构：
    1. video/genvideo/{model}/{model}/{sample_id}.mp4 (嵌套)
    2. video/genvideo/{model}/{sample_id}.mp4
    
    返回：{sample_id: {model1: path, model2: path, ...}}
    """
    videos = {}
    
    if not genvideo_root.exists():
        print(f"  [WARN] Directory not found: {genvideo_root}", flush=True)
        return videos
    
    # 遍历genvideo下的所有目录（每个目录是一个模型）
    for model_dir in genvideo_root.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_name = model_dir.name
        
        # 检查嵌套结构：model/model/
        inner_dir = model_dir / model_name
        if not inner_dir.exists():
            inner_dir = model_dir
        
        # 扫描该模型下的所有mp4文件
        for video_file in inner_dir.glob('*.mp4'):
            sample_id = video_file.stem
            if sample_id not in videos:
                videos[sample_id] = {}
            videos[sample_id][model_name] = video_file
    
    return videos


def get_existing_videos_from_db(db_path: str) -> tuple:
    """
    从数据库获取已存在的视频
    
    返回：(existing_videos_set, existing_models_set)
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 获取已存在的视频 (sample_id, modelname)
    cur.execute("SELECT sample_id, modelname FROM videos WHERE sample_id IS NOT NULL AND modelname IS NOT NULL")
    existing_videos = set(cur.fetchall())
    
    # 获取已存在的模型
    cur.execute("SELECT DISTINCT modelname FROM videos WHERE modelname IS NOT NULL")
    existing_models = set(row[0] for row in cur.fetchall())
    
    conn.close()
    return existing_videos, existing_models


def detect_new_content(scanned_videos: dict, existing_videos: set, existing_models: set) -> tuple:
    """
    检测新增的视频和模型
    
    返回：(new_videos, new_models)
    new_videos: [(sample_id, modelname, file_path), ...]
    new_models: set of model names
    """
    new_videos = []
    new_models = set()
    
    for sample_id, models in scanned_videos.items():
        for model_name, file_path in models.items():
            # 检测新模型
            if model_name not in existing_models:
                new_models.add(model_name)
            
            # 检测新视频
            if (sample_id, model_name) not in existing_videos:
                new_videos.append((sample_id, model_name, file_path))
    
    return new_videos, new_models


def add_new_videos_to_database(db_path: str, new_videos: list, video_base_url: str) -> int:
    """
    将新视频添加到数据库，创建task和assignment
    
    返回：成功添加的视频数量
    """
    if not new_videos:
        return 0
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    added = 0
    video_server_root = Path("video/human_eval_v4/gen")
    
    # 获取所有judges
    cur.execute("SELECT id FROM judges ORDER BY id")
    judges = [row[0] for row in cur.fetchall()]
    
    if not judges:
        print("    [WARN] No judges found in database", flush=True)
        conn.close()
        return 0
    
    for sample_id, model_name, file_path in new_videos:
        try:
            # 检查prompt是否存在
            cur.execute("SELECT id FROM prompts WHERE id = ?", (sample_id,))
            if not cur.fetchone():
                print(f"    [SKIP] {sample_id} has no prompt", flush=True)
                continue
            
            # 获取该sample下的最大variant_index
            cur.execute("SELECT COALESCE(MAX(variant_index), 0) FROM videos WHERE prompt_id = ?", (sample_id,))
            max_variant = cur.fetchone()[0]
            variant_index = max_variant + 1
            
            # 生成视频URL
            video_url = f"{video_base_url}/gen/{sample_id}/{model_name}.mp4"
            
            # 复制视频文件到视频服务器目录
            target_dir = video_server_root / sample_id
            target_file = target_dir / f"{model_name}.mp4"
            
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
            
            if not target_file.exists():
                shutil.copy2(file_path, target_file)
            
            # 插入video记录
            cur.execute("""
                INSERT INTO videos (prompt_id, variant_index, path, modelname, sample_id)
                VALUES (?, ?, ?, ?, ?)
            """, (sample_id, variant_index, video_url, model_name, sample_id))
            
            video_id = cur.lastrowid
            
            # 创建task
            cur.execute("""
                INSERT INTO tasks (prompt_id, video_id, required_ratings, current_ratings, completed)
                VALUES (?, ?, 3, 0, 0)
            """, (sample_id, video_id))
            
            task_id = cur.lastrowid
            
            # 为每个judge创建assignment（添加到末尾，稍后会重新打散）
            for judge_id in judges:
                # 获取该judge当前的最大display_order
                cur.execute("""
                    SELECT COALESCE(MAX(display_order), -1) + 1
                    FROM assignments
                    WHERE judge_id = ?
                """, (judge_id,))
                next_order = cur.fetchone()[0]
                
                # 创建assignment
                cur.execute("""
                    INSERT OR IGNORE INTO assignments (judge_id, task_id, display_order, finished)
                    VALUES (?, ?, ?, 0)
                """, (judge_id, task_id, next_order))
            
            added += 1
            print(f"    [+] {sample_id} / {model_name} (variant {variant_index})", flush=True)
            
        except Exception as e:
            print(f"    [ERROR] {sample_id} / {model_name}: {e}", flush=True)
            conn.rollback()
            continue
    
    conn.commit()
    
    # 重新打散所有未完成的任务
    if added > 0:
        print(f"    [*] Shuffling pending tasks...", flush=True)
        shuffle_pending_tasks(conn, judges)
        conn.commit()
    
    conn.close()
    return added


def shuffle_pending_tasks(conn, judges):
    """随机打散所有judge的未完成任务"""
    cur = conn.cursor()
    seed = random.randint(1, 100000)
    
    for judge_id in judges:
        # 获取已完成和未完成任务
        cur.execute("""
            SELECT id, display_order
            FROM assignments
            WHERE judge_id = ? AND finished = 1
            ORDER BY display_order
        """, (judge_id,))
        finished = cur.fetchall()
        
        cur.execute("""
            SELECT id
            FROM assignments
            WHERE judge_id = ? AND finished = 0
            ORDER BY display_order
        """, (judge_id,))
        pending = [row[0] for row in cur.fetchall()]
        
        if not pending:
            continue
        
        # 找出最大的finished display_order
        max_finished_order = max([order for _, order in finished], default=-1)
        
        # 随机打散未完成任务
        rnd = random.Random(f"{seed}-judge-{judge_id}")
        rnd.shuffle(pending)
        
        # 重新分配display_order
        for new_order, assign_id in enumerate(pending, start=max_finished_order + 1):
            cur.execute("""
                UPDATE assignments SET display_order = ? WHERE id = ?
            """, (new_order, assign_id))
    
    print(f"    [OK] Shuffled with seed: {seed}", flush=True)


def monitor_once(genvideo_root: Path, db_path: str, video_base_url: str):
    """执行一次完整的监控扫描"""
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 70, flush=True)
    print(f"[{timestamp}] Scan started", flush=True)
    print("=" * 70, flush=True)
    
    try:
        # 1. 扫描genvideo目录
        print(f"[1/4] Scanning video files...", flush=True)
        scanned_videos = scan_genvideo_directory(genvideo_root)
        print(f"  Found {len(scanned_videos)} samples", flush=True)
        
        # 统计模型
        all_models = set()
        for models in scanned_videos.values():
            all_models.update(models.keys())
        print(f"  Found {len(all_models)} models: {', '.join(sorted(all_models))}", flush=True)
        
        # 2. 获取数据库中已有的视频
        print(f"[2/4] Reading database...", flush=True)
        existing_videos, existing_models = get_existing_videos_from_db(db_path)
        print(f"  Database has {len(existing_videos)} videos, {len(existing_models)} models", flush=True)
        
        # 3. 检测新增内容
        print(f"[3/4] Detecting new content...", flush=True)
        new_videos, new_models = detect_new_content(scanned_videos, existing_videos, existing_models)
        
        if new_models:
            print(f"  [NEW MODELS] {', '.join(sorted(new_models))}", flush=True)
        
        if new_videos:
            print(f"  Found {len(new_videos)} new videos", flush=True)
            
            # 4. 添加到数据库
            print(f"[4/4] Adding new videos to database...", flush=True)
            added = add_new_videos_to_database(db_path, new_videos, video_base_url)
            print(f"  [OK] Added {added} videos", flush=True)
            
            # 统计每个模型的新增数量
            model_counts = {}
            for _, model, _ in new_videos[:added]:
                model_counts[model] = model_counts.get(model, 0) + 1
            
            print(f"  [SUMMARY]", flush=True)
            for model, count in sorted(model_counts.items()):
                print(f"    {model}: {count} videos", flush=True)
            print(f"  Judges can refresh to see new tasks", flush=True)
        else:
            print(f"[4/4] No new videos found", flush=True)
            print(f"  No changes", flush=True)
        
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{end_time}] Scan complete", flush=True)
        print("=" * 70, flush=True)
        print(flush=True)
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


def monitor_loop(genvideo_root: Path, db_path: str, video_base_url: str, interval: int):
    """监控循环"""
    
    print("=" * 70)
    print("  Simple Video Monitor Service")
    print("=" * 70)
    print(f"\nMonitor directory: {genvideo_root}")
    print(f"Database: {db_path}")
    print(f"Scan interval: {interval} seconds ({interval//60} minutes)")
    print(f"\nPress Ctrl+C to stop\n")
    print("[OK] Service started, preparing first scan...")
    print()
    
    scan_count = 0
    
    try:
        while True:
            scan_count += 1
            success = monitor_once(genvideo_root, db_path, video_base_url)
            
            if not success:
                print("Warning: Scan failed, retry in 60 seconds...", flush=True)
                time.sleep(60)
                continue
            
            if interval > 0:
                print(f"Waiting {interval} seconds for next scan...\n", flush=True)
                time.sleep(interval)
            else:
                break  # --once mode
                
    except KeyboardInterrupt:
        print("\n\nMonitor service stopped")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Simple Video Monitor Service')
    parser.add_argument('--db', default='aiv_eval_v4.db', help='Database path')
    parser.add_argument('--genvideo', default='video/genvideo', help='Generated videos directory')
    parser.add_argument('--interval', type=int, default=300, help='Scan interval (seconds)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    if args.once:
        args.interval = 0
        print("=" * 70)
        print("  Single Scan Mode")
        print("=" * 70)
        print()
    
    genvideo_root = Path(args.genvideo)
    local_ip = get_local_ip()
    video_base_url = f'http://{local_ip}:8010'
    
    monitor_loop(genvideo_root, args.db, video_base_url, args.interval)


if __name__ == '__main__':
    main()

