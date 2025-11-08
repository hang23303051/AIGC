#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 视频监控脚本
自动监控video2目录，检测新增/删除视频，动态更新比较任务
"""

import os
import sqlite3
import time
import random
from pathlib import Path
from collections import defaultdict
import itertools
import argparse

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 配置
DB_PATH = PROJECT_ROOT / "aiv_compare_v1.db"
REF_VIDEO_DIR = PROJECT_ROOT / "video" / "refvideo"
GEN_VIDEO_DIR = PROJECT_ROOT / "video2"
PROMPT_DIR = PROJECT_ROOT / "prompt"

# 监控间隔（秒）
MONITOR_INTERVAL = 300  # 5分钟


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def scan_gen_videos():
    """扫描生成视频目录"""
    gen_videos = defaultdict(list)  # {sample_id: [(model_name, video_path), ...]}
    
    if not GEN_VIDEO_DIR.exists():
        return gen_videos
    
    for model_dir in GEN_VIDEO_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_name = model_dir.name
        sub_dir = model_dir / model_name
        
        if not sub_dir.exists():
            sub_dir = model_dir
        
        for video_file in sub_dir.glob("*.mp4"):
            sample_id = video_file.stem
            video_path = str(video_file.relative_to(PROJECT_ROOT))
            gen_videos[sample_id].append((model_name, video_path))
    
    return gen_videos


def load_prompt_text(sample_id, category):
    """加载Prompt文本"""
    prompt_file = PROMPT_DIR / category / f"{sample_id}.txt"
    
    if prompt_file.exists():
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        return f"[Prompt文件缺失: {sample_id}]"


def get_db_videos():
    """获取数据库中的视频记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT sample_id, model_name, video_path, video_id FROM videos")
    db_videos = {}
    for row in cursor.fetchall():
        key = (row['sample_id'], row['model_name'])
        db_videos[key] = {
            'video_id': row['video_id'],
            'video_path': row['video_path']
        }
    
    conn.close()
    return db_videos


def get_db_tasks():
    """获取数据库中的任务记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT task_id, sample_id, model_a, model_b, completed, current_ratings
        FROM tasks
    """)
    
    db_tasks = {}
    for row in cursor.fetchall():
        key = (row['sample_id'], row['model_a'], row['model_b'])
        db_tasks[key] = {
            'task_id': row['task_id'],
            'completed': row['completed'],
            'current_ratings': row['current_ratings']
        }
    
    conn.close()
    return db_tasks


def get_ref_video_info(sample_id):
    """获取参考视频信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT category, ref_video_path, prompt_text
        FROM prompts
        WHERE sample_id = ?
    """, (sample_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'category': result['category'],
            'ref_video_path': result['ref_video_path'],
            'prompt_text': result['prompt_text']
        }
    
    # 从文件系统查找
    for category_dir in REF_VIDEO_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        
        category_name = category_dir.name
        sub_dir = category_dir / category_name
        
        if not sub_dir.exists():
            continue
        
        video_file = sub_dir / f"{sample_id}.mp4"
        if video_file.exists():
            prompt_text = load_prompt_text(sample_id, category_name)
            return {
                'category': category_name,
                'ref_video_path': str(video_file.relative_to(PROJECT_ROOT)),
                'prompt_text': prompt_text
            }
    
    return None


def add_new_videos(new_videos):
    """添加新视频到数据库"""
    if not new_videos:
        return []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    added_video_ids = {}
    
    for (sample_id, model_name), video_path in new_videos.items():
        # 检查是否有参考视频
        ref_info = get_ref_video_info(sample_id)
        if not ref_info:
            print(f"   ⚠️  跳过 {sample_id}/{model_name}（无参考视频）")
            continue
        
        # 插入或更新prompts
        cursor.execute("""
            INSERT OR IGNORE INTO prompts (sample_id, category, prompt_text, ref_video_path)
            VALUES (?, ?, ?, ?)
        """, (sample_id, ref_info['category'], ref_info['prompt_text'], ref_info['ref_video_path']))
        
        # 插入视频
        cursor.execute("""
            INSERT OR IGNORE INTO videos (sample_id, model_name, video_path)
            VALUES (?, ?, ?)
        """, (sample_id, model_name, video_path))
        
        # 获取video_id
        cursor.execute("""
            SELECT video_id FROM videos WHERE sample_id = ? AND model_name = ?
        """, (sample_id, model_name))
        
        video_id = cursor.fetchone()['video_id']
        added_video_ids[(sample_id, model_name)] = video_id
    
    conn.commit()
    conn.close()
    
    return added_video_ids


def create_new_tasks(gen_videos):
    """为新视频创建比较任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    new_tasks = []
    
    # 获取所有评审员
    cursor.execute("SELECT judge_id FROM judges")
    judge_ids = [row['judge_id'] for row in cursor.fetchall()]
    
    for sample_id, models in gen_videos.items():
        if len(models) < 2:
            continue
        
        # 生成所有配对
        for (model_a, _), (model_b, _) in itertools.combinations(models, 2):
            # 确保字母序
            if model_a > model_b:
                model_a, model_b = model_b, model_a
            
            # 检查任务是否存在
            cursor.execute("""
                SELECT task_id FROM tasks
                WHERE sample_id = ? AND model_a = ? AND model_b = ?
            """, (sample_id, model_a, model_b))
            
            if cursor.fetchone():
                continue
            
            # 获取video_id
            cursor.execute("""
                SELECT video_id FROM videos WHERE sample_id = ? AND model_name = ?
            """, (sample_id, model_a))
            video_a_id = cursor.fetchone()['video_id']
            
            cursor.execute("""
                SELECT video_id FROM videos WHERE sample_id = ? AND model_name = ?
            """, (sample_id, model_b))
            video_b_id = cursor.fetchone()['video_id']
            
            # 创建任务
            cursor.execute("""
                INSERT INTO tasks (sample_id, model_a, model_b, video_a_id, video_b_id)
                VALUES (?, ?, ?, ?, ?)
            """, (sample_id, model_a, model_b, video_a_id, video_b_id))
            
            task_id = cursor.lastrowid
            new_tasks.append((task_id, sample_id, model_a, model_b))
            
            # 为所有评审员分配任务
            for judge_id in judge_ids:
                # 获取该评审员当前最大position
                cursor.execute("""
                    SELECT COALESCE(MAX(position), 0) as max_pos
                    FROM assignments
                    WHERE judge_id = ?
                """, (judge_id,))
                max_pos = cursor.fetchone()['max_pos']
                
                # 随机插入位置（在未完成任务中）
                cursor.execute("""
                    SELECT COUNT(*) as pending_count
                    FROM assignments a
                    JOIN tasks t ON a.task_id = t.task_id
                    WHERE a.judge_id = ? AND t.completed = 0
                """, (judge_id,))
                pending_count = cursor.fetchone()['pending_count']
                
                if pending_count > 0:
                    random_pos = random.randint(1, pending_count + 1)
                    
                    # 更新后续任务的position
                    cursor.execute("""
                        UPDATE assignments
                        SET position = position + 1
                        WHERE judge_id = ? AND position >= ?
                    """, (judge_id, random_pos))
                    
                    new_position = random_pos
                else:
                    new_position = max_pos + 1
                
                cursor.execute("""
                    INSERT INTO assignments (judge_id, task_id, position)
                    VALUES (?, ?, ?)
                """, (judge_id, task_id, new_position))
    
    conn.commit()
    conn.close()
    
    return new_tasks


def cleanup_deleted_videos(deleted_videos):
    """清理已删除视频的未完成任务"""
    if not deleted_videos:
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    deleted_task_count = 0
    
    for sample_id, model_name in deleted_videos:
        # 删除涉及该视频的未完成任务
        cursor.execute("""
            DELETE FROM tasks
            WHERE (
                (sample_id = ? AND model_a = ?)
                OR (sample_id = ? AND model_b = ?)
            )
            AND completed = 0
            AND current_ratings = 0
        """, (sample_id, model_name, sample_id, model_name))
        
        deleted_task_count += cursor.rowcount
        
        # 删除视频记录（如果没有相关评分）
        cursor.execute("""
            DELETE FROM videos
            WHERE sample_id = ? AND model_name = ?
            AND NOT EXISTS (
                SELECT 1 FROM tasks t
                JOIN comparisons c ON t.task_id = c.task_id
                WHERE (t.sample_id = ? AND (t.model_a = ? OR t.model_b = ?))
            )
        """, (sample_id, model_name, sample_id, model_name, model_name))
    
    conn.commit()
    conn.close()
    
    return deleted_task_count


def monitor_once():
    """执行一次监控"""
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始扫描...")
    
    # 扫描文件系统
    fs_videos = scan_gen_videos()
    fs_videos_flat = {}
    for sample_id, models in fs_videos.items():
        for model_name, video_path in models:
            fs_videos_flat[(sample_id, model_name)] = video_path
    
    # 获取数据库记录
    db_videos = get_db_videos()
    
    # 检测新增视频
    new_videos = {}
    for key, video_path in fs_videos_flat.items():
        if key not in db_videos:
            new_videos[key] = video_path
    
    # 检测删除视频
    deleted_videos = []
    for key in db_videos:
        if key not in fs_videos_flat:
            deleted_videos.append(key)
    
    # 处理新增
    if new_videos:
        print(f"\n📹 检测到 {len(new_videos)} 个新增视频")
        for (sample_id, model_name), video_path in new_videos.items():
            print(f"   + {sample_id}/{model_name}")
        
        add_new_videos(new_videos)
        new_tasks = create_new_tasks(fs_videos)
        
        if new_tasks:
            print(f"\n✅ 创建 {len(new_tasks)} 个新任务")
            for task_id, sample_id, model_a, model_b in new_tasks[:5]:
                print(f"   {sample_id}: {model_a} vs {model_b}")
            if len(new_tasks) > 5:
                print(f"   ... 还有 {len(new_tasks)-5} 个任务")
    
    # 处理删除
    if deleted_videos:
        print(f"\n🗑️  检测到 {len(deleted_videos)} 个删除视频")
        for sample_id, model_name in deleted_videos[:5]:
            print(f"   - {sample_id}/{model_name}")
        if len(deleted_videos) > 5:
            print(f"   ... 还有 {len(deleted_videos)-5} 个")
        
        deleted_count = cleanup_deleted_videos(deleted_videos)
        print(f"\n🧹 清理 {deleted_count} 个未完成任务")
    
    if not new_videos and not deleted_videos:
        print("   无变化")
    
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 扫描完成")


def main():
    parser = argparse.ArgumentParser(description='比较评测模式 - 视频监控')
    parser.add_argument('--once', action='store_true',
                        help='只执行一次扫描后退出')
    parser.add_argument('--interval', type=int, default=MONITOR_INTERVAL,
                        help=f'监控间隔（秒，默认{MONITOR_INTERVAL}）')
    
    args = parser.parse_args()
    
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        print("   请先运行: python scripts\\setup_project_compare.py")
        return
    
    print("="*80)
    print("比较评测模式 - 视频监控")
    print("="*80)
    
    if args.once:
        monitor_once()
    else:
        print(f"⏰ 监控间隔: {args.interval} 秒")
        print("按 Ctrl+C 停止监控\n")
        
        try:
            while True:
                monitor_once()
                print(f"\n⏳ 等待 {args.interval} 秒...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")


if __name__ == "__main__":
    main()

