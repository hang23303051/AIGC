#!/usr/bin/env python3
"""
V1 → V2 数据库迁移脚本（正确处理已有评分）

核心逻辑：
1. 保留所有已有评分
2. 对于每个任务，统计已被评了几次（current_ratings）
3. 对于已评过该任务的judge，创建finished=1的assignment
4. 对于未评过该任务的judge，创建finished=0的assignment
5. 如果任务已被评3次，标记为completed=1，不再创建新的assignments
"""

import sqlite3
import os
import random
from collections import defaultdict
from datetime import datetime

def read_v1_data(old_db: str) -> dict:
    """读取V1数据库"""
    print("\n" + "=" * 70)
    print("  Step 1: 读取V1数据库")
    print("=" * 70)
    
    conn = sqlite3.connect(old_db)
    cur = conn.cursor()
    
    data = {}
    
    # 读取judges
    cur.execute("SELECT id, name, token FROM judges")
    data['judges'] = cur.fetchall()
    print(f"✓ 读取 {len(data['judges'])} 个评审员")
    
    # 读取prompts
    cur.execute("SELECT id, text, ref_path FROM prompts")
    data['prompts'] = cur.fetchall()
    print(f"✓ 读取 {len(data['prompts'])} 个prompts")
    
    # 读取videos
    cur.execute("SELECT id, prompt_id, variant_index, path, modelname, sample_id FROM videos")
    data['videos'] = cur.fetchall()
    print(f"✓ 读取 {len(data['videos'])} 个videos")
    
    # 读取ratings（V1表结构：id, judge_id, video_id, scores, modelname, sample_id, created_at）
    cur.execute("""
        SELECT id, judge_id, video_id,
               score_semantic, score_motion, score_temporal, score_realism,
               modelname, sample_id, created_at
        FROM ratings
    """)
    data['ratings'] = cur.fetchall()
    print(f"✓ 读取 {len(data['ratings'])} 个ratings")
    
    conn.close()
    
    return data


def analyze_ratings(data: dict) -> dict:
    """分析每个视频的评分情况"""
    print("\n" + "=" * 70)
    print("  Step 2: 分析评分情况")
    print("=" * 70)
    
    # 统计每个视频被哪些judge评了
    video_judges = defaultdict(set)  # {video_id: set(judge_ids)}
    
    for rating in data['ratings']:
        # V1 rating格式: (id, judge_id, video_id, score_semantic, score_motion, score_temporal, score_realism, modelname, sample_id, created_at)
        rating_id, judge_id, video_id = rating[0], rating[1], rating[2]
        video_judges[video_id].add(judge_id)
    
    stats = {
        'video_judges': video_judges,
        'completed_tasks': 0,      # 已完成3次评测的任务
        'partial_tasks': 0,         # 部分完成（1-2次）的任务
        'unstarted_tasks': 0,       # 未开始的任务
    }
    
    # 统计任务完成度
    for video in data['videos']:
        video_id = video[0]
        count = len(video_judges.get(video_id, set()))
        if count >= 3:
            stats['completed_tasks'] += 1
        elif count > 0:
            stats['partial_tasks'] += 1
        else:
            stats['unstarted_tasks'] += 1
    
    print(f"✓ 总任务数: {len(data['videos'])}")
    print(f"  - 已完成（≥3次评测）: {stats['completed_tasks']}")
    print(f"  - 部分完成（1-2次）: {stats['partial_tasks']}")
    print(f"  - 未开始: {stats['unstarted_tasks']}")
    print(f"✓ 总评分数: {len(data['ratings'])}")
    
    # 显示每个评分次数的任务分布
    rating_counts = defaultdict(int)
    for video in data['videos']:
        video_id = video[0]
        count = len(video_judges.get(video_id, set()))
        rating_counts[count] += 1
    
    print(f"\n任务评分次数分布:")
    for count in sorted(rating_counts.keys()):
        print(f"  被评{count}次: {rating_counts[count]} 个任务")
    
    return stats


def create_v2_database(new_db: str, schema_file: str):
    """创建V2数据库"""
    print("\n" + "=" * 70)
    print("  Step 3: 创建V2数据库")
    print("=" * 70)
    
    if os.path.exists(new_db):
        backup = f"{new_db}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(new_db, backup)
        print(f"✓ 已存在数据库已备份到: {backup}")
    
    conn = sqlite3.connect(new_db)
    
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema = f.read()
        conn.executescript(schema)
    
    conn.commit()
    conn.close()
    
    print(f"✓ V2数据库已创建: {new_db}")


def migrate_base_tables(old_data: dict, new_db: str):
    """迁移基础表数据"""
    print("\n" + "=" * 70)
    print("  Step 4: 迁移基础表数据")
    print("=" * 70)
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    
    # 迁移judges
    for judge in old_data['judges']:
        cur.execute("""
            INSERT INTO judges (id, name, token) VALUES (?, ?, ?)
        """, judge)
    print(f"✓ 迁移 {len(old_data['judges'])} 个评审员")
    
    # 迁移prompts
    for prompt in old_data['prompts']:
        cur.execute("""
            INSERT INTO prompts (id, text, ref_path) VALUES (?, ?, ?)
        """, prompt)
    print(f"✓ 迁移 {len(old_data['prompts'])} 个prompts")
    
    # 迁移videos
    for video in old_data['videos']:
        cur.execute("""
            INSERT INTO videos (id, prompt_id, variant_index, path, modelname, sample_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, video)
    print(f"✓ 迁移 {len(old_data['videos'])} 个videos")
    
    conn.commit()
    conn.close()


def migrate_ratings(old_data: dict, stats: dict, new_db: str):
    """迁移评分数据"""
    print("\n" + "=" * 70)
    print("  Step 5: 迁移评分数据")
    print("=" * 70)
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    
    # 迁移ratings - 需要补充prompt_id字段
    for rating in old_data['ratings']:
        # V1 rating格式: (id, judge_id, video_id, score_semantic, score_motion, score_temporal, score_realism, modelname, sample_id, created_at)
        rating_id, judge_id, video_id = rating[0], rating[1], rating[2]
        score_semantic, score_motion, score_temporal, score_realism = rating[3], rating[4], rating[5], rating[6]
        modelname, sample_id, created_at = rating[7], rating[8], rating[9]
        
        # 从videos表获取prompt_id
        cur.execute("SELECT prompt_id FROM videos WHERE id = ?", (video_id,))
        result = cur.fetchone()
        if not result:
            print(f"  [WARN] Rating {rating_id} 的 video_id {video_id} 不存在，跳过")
            continue
        prompt_id = result[0]
        
        cur.execute("""
            INSERT INTO ratings 
            (id, judge_id, prompt_id, video_id, modelname, sample_id,
             score_semantic, score_motion, score_temporal, score_realism,
             created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (rating_id, judge_id, prompt_id, video_id, modelname, sample_id,
              score_semantic, score_motion, score_temporal, score_realism, created_at))
    
    conn.commit()
    conn.close()
    
    print(f"✓ 迁移 {len(old_data['ratings'])} 个评分记录")


def create_tasks_and_assignments(old_data: dict, stats: dict, new_db: str, seed: int = 42):
    """创建tasks和assignments（正确处理已有评分）"""
    print("\n" + "=" * 70)
    print("  Step 6: 创建tasks和assignments")
    print("=" * 70)
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    
    video_judges = stats['video_judges']
    
    all_judges = [j[0] for j in old_data['judges']]
    all_videos = [(v[0], v[1]) for v in old_data['videos']]  # (video_id, prompt_id)
    
    tasks_created = 0
    assignments_created = 0
    completed_tasks = 0
    
    # 为每个video创建task
    for video_id, prompt_id in all_videos:
        judges_who_rated = video_judges.get(video_id, set())
        current_ratings = len(judges_who_rated)
        completed = 1 if current_ratings >= 3 else 0
        
        # 创建task
        cur.execute("""
            INSERT INTO tasks (prompt_id, video_id, required_ratings, current_ratings, completed)
            VALUES (?, ?, 3, ?, ?)
        """, (prompt_id, video_id, current_ratings, completed))
        task_id = cur.lastrowid
        tasks_created += 1
        
        if completed:
            completed_tasks += 1
            # 已完成的任务：只为已评过的judge创建finished=1的assignment
            for judge_id in judges_who_rated:
                cur.execute("""
                    INSERT INTO assignments (judge_id, task_id, display_order, finished, finished_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (judge_id, task_id, 0))  # display_order不重要，因为已完成
                assignments_created += 1
        else:
            # 未完成的任务：为所有judge创建assignment
            # - 已评过的：finished=1
            # - 未评过的：finished=0
            
            # 为所有judge生成随机顺序
            judge_order = {j: None for j in all_judges}
            shuffled_judges = all_judges.copy()
            random.Random(f"{seed}-task-{task_id}").shuffle(shuffled_judges)
            for order, judge_id in enumerate(shuffled_judges):
                judge_order[judge_id] = order
            
            for judge_id in all_judges:
                if judge_id in judges_who_rated:
                    # 已评过：finished=1
                    cur.execute("""
                        INSERT INTO assignments (judge_id, task_id, display_order, finished, finished_at)
                        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """, (judge_id, task_id, judge_order[judge_id]))
                else:
                    # 未评过：finished=0
                    cur.execute("""
                        INSERT INTO assignments (judge_id, task_id, display_order, finished)
                        VALUES (?, ?, ?, 0)
                    """, (judge_id, task_id, judge_order[judge_id]))
                assignments_created += 1
    
    conn.commit()
    
    print(f"✓ 创建 {tasks_created} 个tasks")
    print(f"  - 已完成: {completed_tasks}")
    print(f"  - 未完成: {tasks_created - completed_tasks}")
    print(f"✓ 创建 {assignments_created} 个assignments")
    
    # 显示每个judge的进度
    print(f"\n各评审员进度:")
    for judge in old_data['judges']:
        judge_id, judge_name = judge[0], judge[1]
        
        cur.execute("""
            SELECT COUNT(*) FROM assignments WHERE judge_id = ? AND finished = 1
        """, (judge_id,))
        finished = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM assignments a
            JOIN tasks t ON a.task_id = t.id
            WHERE a.judge_id = ? AND a.finished = 0 AND t.completed = 0
        """, (judge_id,))
        pending = cur.fetchone()[0]
        
        total = finished + pending
        pct = (finished / total * 100) if total > 0 else 0
        print(f"  {judge_name:<15} 已完成:{finished:>4} / 待做:{pending:>4} / 总:{total:>4} ({pct:>5.1f}%)")
    
    conn.close()


def verify_migration(new_db: str):
    """验证迁移结果"""
    print("\n" + "=" * 70)
    print("  Step 7: 验证迁移结果")
    print("=" * 70)
    
    conn = sqlite3.connect(new_db)
    cur = conn.cursor()
    
    # 基础数据
    cur.execute("SELECT COUNT(*) FROM judges")
    judges_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM prompts")
    prompts_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM videos")
    videos_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM ratings")
    ratings_count = cur.fetchone()[0]
    
    print(f"✓ 基础数据:")
    print(f"  - 评审员: {judges_count}")
    print(f"  - Prompts: {prompts_count}")
    print(f"  - Videos: {videos_count}")
    print(f"  - Ratings: {ratings_count}")
    
    # 新表数据
    cur.execute("SELECT COUNT(*) FROM tasks")
    tasks_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM assignments")
    assignments_count = cur.fetchone()[0]
    
    print(f"\n✓ 新表数据:")
    print(f"  - Tasks: {tasks_count}")
    print(f"  - Assignments: {assignments_count}")
    
    # 任务完成统计
    cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=1")
    completed = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=0")
    pending = cur.fetchone()[0]
    
    cur.execute("SELECT SUM(current_ratings) FROM tasks")
    total_ratings = cur.fetchone()[0] or 0
    
    print(f"\n✓ 任务完成统计:")
    print(f"  - 总任务数: {tasks_count}")
    print(f"  - 已完成: {completed}")
    print(f"  - 未完成: {pending}")
    print(f"  - 当前评分数: {total_ratings}")
    print(f"  - 需要评分总数: {tasks_count * 3}")
    print(f"  - 完成率: {(completed / tasks_count * 100) if tasks_count > 0 else 0:.2f}%")
    
    # 任务评分次数分布
    cur.execute("""
        SELECT current_ratings, COUNT(*) 
        FROM tasks 
        GROUP BY current_ratings 
        ORDER BY current_ratings
    """)
    print(f"\n✓ 任务评分次数分布:")
    for count, num in cur.fetchall():
        status = "✓ 已完成" if count >= 3 else "进行中"
        print(f"  被评{count}次: {num:>5} 个任务 {status}")
    
    # 数据一致性检查
    cur.execute("""
        SELECT COUNT(*) FROM tasks t
        WHERE t.current_ratings != (
            SELECT COUNT(DISTINCT judge_id) FROM ratings WHERE video_id = t.video_id
        )
    """)
    inconsistent = cur.fetchone()[0]
    
    if inconsistent > 0:
        print(f"\n⚠️  警告: {inconsistent} 个task的评分计数不一致")
    else:
        print(f"\n✓ 数据一致性检查: 通过")
    
    conn.close()


def main():
    import argparse
    
    ap = argparse.ArgumentParser(description="V1 → V2 数据库迁移（正确处理已有评分）")
    ap.add_argument("--old-db", default="backup/aiv_eval_v4_v1_backup.db", help="旧数据库路径")
    ap.add_argument("--new-db", default="aiv_eval_v4_v2.db", help="新数据库路径")
    ap.add_argument("--schema", default="db/schema.sql", help="Schema文件路径")
    ap.add_argument("--seed", type=int, default=42, help="随机种子")
    args = ap.parse_args()
    
    print("=" * 70)
    print("  AIV评测系统数据库迁移")
    print("  V1 (每任务所有人评) -> V2 (每任务3人评)")
    print("=" * 70)
    print(f"\n旧数据库: {args.old_db}")
    print(f"新数据库: {args.new_db}")
    print(f"Schema: {args.schema}")
    
    if not os.path.exists(args.old_db):
        print(f"\n❌ 错误: 旧数据库不存在: {args.old_db}")
        return 1
    
    if not os.path.exists(args.schema):
        print(f"\n❌ 错误: Schema文件不存在: {args.schema}")
        return 1
    
    confirm = input("\n确认开始迁移？(yes/no): ")
    if confirm.lower() != 'yes':
        print("迁移已取消")
        return 0
    
    # 执行迁移
    old_data = read_v1_data(args.old_db)
    stats = analyze_ratings(old_data)
    create_v2_database(args.new_db, args.schema)
    migrate_base_tables(old_data, args.new_db)
    migrate_ratings(old_data, stats, args.new_db)
    create_tasks_and_assignments(old_data, stats, args.new_db, args.seed)
    verify_migration(args.new_db)
    
    print("\n" + "=" * 70)
    print("  迁移完成！")
    print("=" * 70)
    print("\n✅ 迁移成功完成！")
    print("\n下一步:")
    print(f"  1. 备份旧数据库: mv {args.old_db.replace('backup/', '')} {args.old_db}")
    print(f"  2. 启用新数据库: mv {args.new_db} aiv_eval_v4.db")
    print(f"  3. 重启服务: .\\lan_start_with_monitor.ps1")
    
    return 0


if __name__ == '__main__':
    exit(main())

