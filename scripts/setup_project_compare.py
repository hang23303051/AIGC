#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 项目初始化脚本
创建数据库、导入任务、创建评审员、分配任务
"""

import sqlite3
import csv
import uuid
import random
import argparse
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 配置
SCHEMA_FILE = PROJECT_ROOT / "db" / "schema_compare.sql"
CSV_FILE = PROJECT_ROOT / "data" / "comparison_tasks.csv"
DEFAULT_DB = PROJECT_ROOT / "aiv_compare_v1.db"


def create_database(db_path, schema_file):
    """创建数据库并执行schema"""
    print(f"📦 创建数据库: {db_path}")
    
    # 删除旧数据库（如果存在）
    if db_path.exists():
        print(f"   ⚠️  删除旧数据库...")
        db_path.unlink()
    
    # 读取schema
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # 创建数据库
    conn = sqlite3.connect(db_path)
    conn.executescript(schema_sql)
    conn.commit()
    
    print(f"   ✅ 数据库创建成功")
    return conn


def create_judges(conn, num_judges):
    """创建评审员账户"""
    print(f"\n👥 创建 {num_judges} 个评审员账户...")
    
    judges = []
    for i in range(1, num_judges + 1):
        uid = str(uuid.uuid4())
        judge_name = f"Judge-{i:02d}"
        judges.append((uid, judge_name))
    
    conn.executemany(
        "INSERT INTO judges (uid, judge_name) VALUES (?, ?)",
        judges
    )
    conn.commit()
    
    print(f"   ✅ 创建成功")
    return judges


def import_prompts_and_videos(conn, csv_file):
    """导入参考视频和生成视频信息"""
    print(f"\n📋 导入任务清单: {csv_file}")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"   读取 {len(rows)} 条任务记录")
    
    # 1. 导入prompts（去重）
    print("   导入参考视频...")
    prompts_dict = {}
    for row in rows:
        sample_id = row['sample_id']
        if sample_id not in prompts_dict:
            prompts_dict[sample_id] = {
                'sample_id': sample_id,
                'category': row['category'],
                'prompt_text': row['prompt_text'],
                'ref_video_path': row['ref_video_path']
            }
    
    conn.executemany(
        """INSERT OR IGNORE INTO prompts (sample_id, category, prompt_text, ref_video_path)
           VALUES (:sample_id, :category, :prompt_text, :ref_video_path)""",
        prompts_dict.values()
    )
    print(f"      ✅ 导入 {len(prompts_dict)} 个参考视频")
    
    # 2. 导入videos（去重）
    print("   导入生成视频...")
    videos_dict = {}
    for row in rows:
        # 模型A
        key_a = (row['sample_id'], row['model_a'])
        if key_a not in videos_dict:
            videos_dict[key_a] = {
                'sample_id': row['sample_id'],
                'model_name': row['model_a'],
                'video_path': row['video_a_path']
            }
        
        # 模型B
        key_b = (row['sample_id'], row['model_b'])
        if key_b not in videos_dict:
            videos_dict[key_b] = {
                'sample_id': row['sample_id'],
                'model_name': row['model_b'],
                'video_path': row['video_b_path']
            }
    
    conn.executemany(
        """INSERT OR IGNORE INTO videos (sample_id, model_name, video_path)
           VALUES (:sample_id, :model_name, :video_path)""",
        videos_dict.values()
    )
    print(f"      ✅ 导入 {len(videos_dict)} 个生成视频")
    
    conn.commit()
    
    return rows


def create_comparison_tasks(conn, task_rows):
    """创建比较任务"""
    print(f"\n⚙️  创建比较任务...")
    
    tasks_created = 0
    for row in task_rows:
        # 获取video_id
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT video_id FROM videos WHERE sample_id=? AND model_name=?",
            (row['sample_id'], row['model_a'])
        )
        video_a_id = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT video_id FROM videos WHERE sample_id=? AND model_name=?",
            (row['sample_id'], row['model_b'])
        )
        video_b_id = cursor.fetchone()[0]
        
        # 插入任务
        cursor.execute(
            """INSERT OR IGNORE INTO tasks 
               (sample_id, model_a, model_b, video_a_id, video_b_id)
               VALUES (?, ?, ?, ?, ?)""",
            (row['sample_id'], row['model_a'], row['model_b'], video_a_id, video_b_id)
        )
        
        if cursor.rowcount > 0:
            tasks_created += 1
    
    conn.commit()
    print(f"   ✅ 创建 {tasks_created} 个比较任务")
    
    return tasks_created


def assign_tasks_to_judges(conn):
    """为所有评审员分配任务（随机顺序）"""
    print(f"\n🎲 为评审员分配任务...")
    
    cursor = conn.cursor()
    
    # 获取所有评审员
    cursor.execute("SELECT judge_id FROM judges")
    judge_ids = [row[0] for row in cursor.fetchall()]
    
    # 获取所有未完成的任务
    cursor.execute("SELECT task_id FROM tasks WHERE completed = 0")
    task_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"   评审员数量: {len(judge_ids)}")
    print(f"   任务数量: {len(task_ids)}")
    
    # 为每个评审员分配所有任务，但顺序随机
    total_assignments = 0
    for judge_id in judge_ids:
        # 随机打散任务顺序
        shuffled_tasks = task_ids.copy()
        random.shuffle(shuffled_tasks)
        
        # 插入分配记录
        assignments = [
            (judge_id, task_id, position)
            for position, task_id in enumerate(shuffled_tasks, start=1)
        ]
        
        cursor.executemany(
            "INSERT INTO assignments (judge_id, task_id, position) VALUES (?, ?, ?)",
            assignments
        )
        
        total_assignments += len(assignments)
    
    conn.commit()
    print(f"   ✅ 完成 {total_assignments} 条任务分配")


def show_summary(conn):
    """显示统计信息"""
    print("\n" + "="*80)
    print("📊 初始化完成统计")
    print("="*80)
    
    cursor = conn.cursor()
    
    # 评审员数量
    cursor.execute("SELECT COUNT(*) FROM judges")
    num_judges = cursor.fetchone()[0]
    print(f"👥 评审员: {num_judges} 人")
    
    # 参考视频数量
    cursor.execute("SELECT COUNT(*) FROM prompts")
    num_prompts = cursor.fetchone()[0]
    print(f"📹 参考视频: {num_prompts} 个")
    
    # 生成视频数量
    cursor.execute("SELECT COUNT(*) FROM videos")
    num_videos = cursor.fetchone()[0]
    print(f"🤖 生成视频: {num_videos} 个")
    
    # 比较任务数量
    cursor.execute("SELECT COUNT(*) FROM tasks")
    num_tasks = cursor.fetchone()[0]
    print(f"📋 比较任务: {num_tasks} 个")
    
    # 总评测次数
    total_comparisons = num_tasks * 3
    print(f"🎯 需要评测次数: {total_comparisons} 次 (每任务3次)")
    
    # 模型分布
    cursor.execute("""
        SELECT model_name, COUNT(*) 
        FROM videos 
        GROUP BY model_name 
        ORDER BY COUNT(*) DESC
    """)
    print(f"\n🤖 模型分布:")
    for model_name, count in cursor.fetchall():
        print(f"   {model_name}: {count} 个视频")


def main():
    parser = argparse.ArgumentParser(description='比较评测模式 - 项目初始化')
    parser.add_argument('--db', type=str, default=str(DEFAULT_DB),
                        help=f'数据库文件路径 (默认: {DEFAULT_DB.name})')
    parser.add_argument('--csv', type=str, default=str(CSV_FILE),
                        help=f'任务清单CSV文件 (默认: {CSV_FILE})')
    parser.add_argument('--judges', type=int, default=10,
                        help='评审员数量 (默认: 10)')
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    csv_file = Path(args.csv)
    
    # 检查文件
    if not SCHEMA_FILE.exists():
        print(f"❌ Schema文件不存在: {SCHEMA_FILE}")
        return
    
    if not csv_file.exists():
        print(f"❌ CSV文件不存在: {csv_file}")
        print(f"   请先运行: python scripts\\prepare_data_compare.py")
        return
    
    print("="*80)
    print("比较评测模式 - 项目初始化")
    print("="*80)
    
    # 1. 创建数据库
    conn = create_database(db_path, SCHEMA_FILE)
    
    # 2. 创建评审员
    judges = create_judges(conn, args.judges)
    
    # 3. 导入参考视频和生成视频
    task_rows = import_prompts_and_videos(conn, csv_file)
    
    # 4. 创建比较任务
    create_comparison_tasks(conn, task_rows)
    
    # 5. 分配任务给评审员
    assign_tasks_to_judges(conn)
    
    # 6. 显示统计
    show_summary(conn)
    
    # 7. 保存评审员链接到文件
    print(f"\n💾 保存评审员链接到: judge_links_compare.txt")
    with open(PROJECT_ROOT / "judge_links_compare.txt", 'w', encoding='utf-8') as f:
        f.write("比较评测模式 - 评审员访问链接\n")
        f.write("="*80 + "\n\n")
        for uid, judge_name in judges:
            f.write(f"{judge_name}: http://<本机IP>:8503/?uid={uid}\n")
    
    conn.close()
    
    print("\n" + "="*80)
    print("✅ 项目初始化完成！")
    print("="*80)
    print("\n下一步:")
    print("1. 配置防火墙（如需要）: .\\scripts\\setup_firewall_compare.ps1")
    print("2. 启动服务: .\\lan_start_compare.ps1")
    print("3. 获取评审员链接: python get_links_compare.py")


if __name__ == "__main__":
    main()

