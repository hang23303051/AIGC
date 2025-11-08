#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 详细进度查看脚本
显示任务完成情况、评审员进度、任务评测次数分布等统计信息
"""

import sqlite3
from pathlib import Path
from collections import defaultdict

# 配置
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "aiv_compare_v1.db"


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def show_task_rating_distribution():
    """显示任务评测次数分布（0次、1次、2次、3次）"""
    print("\n📊 任务评测次数分布:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 统计每个评测次数的任务数量
    cursor.execute("""
        SELECT 
            current_ratings,
            COUNT(*) as task_count
        FROM tasks
        GROUP BY current_ratings
        ORDER BY current_ratings
    """)
    
    rating_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    total_tasks = 0
    
    for row in cursor.fetchall():
        rating_count = row['current_ratings']
        task_count = row['task_count']
        rating_counts[rating_count] = task_count
        total_tasks += task_count
    
    print(f"  总任务数: {total_tasks}")
    print(f"\n  评测次数分布:")
    print(f"    未被评（0次）: {rating_counts[0]} 个任务 ({rating_counts[0]/total_tasks*100:.1f}%)" if total_tasks > 0 else "    未被评（0次）: 0 个任务")
    print(f"    被评1次:      {rating_counts[1]} 个任务 ({rating_counts[1]/total_tasks*100:.1f}%)" if total_tasks > 0 else "    被评1次:      0 个任务")
    print(f"    被评2次:      {rating_counts[2]} 个任务 ({rating_counts[2]/total_tasks*100:.1f}%)" if total_tasks > 0 else "    被评2次:      0 个任务")
    print(f"    已完成（3次）: {rating_counts[3]} 个任务 ({rating_counts[3]/total_tasks*100:.1f}%)" if total_tasks > 0 else "    已完成（3次）: 0 个任务")
    
    # 计算还需多少次评测才能全部完成
    remaining_comparisons = (rating_counts[0] * 3 + rating_counts[1] * 2 + rating_counts[2] * 1)
    print(f"\n  还需评测总数: {remaining_comparisons} 次")
    print(f"  已完成评测数: {rating_counts[1] + rating_counts[2]*2 + rating_counts[3]*3} 次")
    
    conn.close()


def show_task_progress():
    """显示任务进度"""
    print("\n📈 任务完成情况:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 总任务数
    cursor.execute("SELECT COUNT(*) as total FROM tasks")
    total_tasks = cursor.fetchone()['total']
    
    # 已完成任务数
    cursor.execute("SELECT COUNT(*) as completed FROM tasks WHERE completed = 1")
    completed_tasks = cursor.fetchone()['completed']
    
    # 未完成任务数
    pending_tasks = total_tasks - completed_tasks
    
    # 完成率
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    print(f"  总任务数:    {total_tasks}")
    print(f"  已完成:      {completed_tasks}")
    print(f"  未完成:      {pending_tasks}")
    print(f"  完成率:      {completion_rate:.2f}%")
    
    # 进度条
    bar_length = 50
    filled_length = int(bar_length * completion_rate / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    print(f"  进度条:      [{bar}] {completion_rate:.1f}%")
    
    conn.close()


def show_judge_detailed_progress():
    """显示每个评审员的详细进度"""
    print("\n👥 评审员详细进度:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取总任务数
    cursor.execute("SELECT COUNT(*) as total FROM tasks")
    total_tasks = cursor.fetchone()['total']
    
    # 获取每个评审员的进度
    cursor.execute("""
        SELECT 
            j.judge_id,
            j.judge_name,
            COUNT(DISTINCT a.task_id) as assigned_tasks,
            COUNT(DISTINCT c.task_id) as completed_tasks
        FROM judges j
        LEFT JOIN assignments a ON j.judge_id = a.judge_id
        LEFT JOIN comparisons c ON j.judge_id = c.judge_id
        GROUP BY j.judge_id, j.judge_name
        ORDER BY j.judge_name
    """)
    
    judges = cursor.fetchall()
    
    print(f"  {'评审员':<12} {'已完成':<8} {'待评任务':<10} {'完成率':<10} {'进度条':<30}")
    print(f"  {'-'*78}")
    
    for judge in judges:
        judge_name = judge['judge_name']
        assigned = judge['assigned_tasks']
        completed = judge['completed_tasks']
        pending = assigned - completed
        percentage = (completed / assigned * 100) if assigned > 0 else 0
        
        # 小进度条
        bar_length = 20
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"  {judge_name:<12} {completed:<8} {pending:<10} {percentage:>6.1f}%    [{bar}]")
    
    # 统计信息
    cursor.execute("SELECT COUNT(*) as total FROM comparisons")
    total_comparisons = cursor.fetchone()['total']
    
    avg_per_judge = total_comparisons / len(judges) if len(judges) > 0 else 0
    
    print(f"\n  总评测次数: {total_comparisons}")
    print(f"  平均每人:   {avg_per_judge:.1f} 次")
    
    conn.close()


def show_model_comparison():
    """显示模型比较统计"""
    print("\n🤖 模型比较统计:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 每个模型的任务数
    cursor.execute("""
        SELECT model_name, COUNT(*) as task_count
        FROM (
            SELECT model_a as model_name FROM tasks
            UNION ALL
            SELECT model_b as model_name FROM tasks
        )
        GROUP BY model_name
        ORDER BY task_count DESC
    """)
    
    print("  各模型参与的比较任务数:")
    for row in cursor.fetchall():
        print(f"    {row['model_name']:<15}: {row['task_count']:>4} 个任务")
    
    # 模型胜率统计（只统计已完成评测的）
    cursor.execute("""
        SELECT 
            chosen_model,
            COUNT(*) as win_count
        FROM comparisons
        WHERE chosen_model != 'tie'
        GROUP BY chosen_model
        ORDER BY win_count DESC
    """)
    
    print("\n  模型胜出统计（已完成评测）:")
    total_wins = 0
    win_stats = []
    for row in cursor.fetchall():
        win_count = row['win_count']
        total_wins += win_count
        win_stats.append((row['chosen_model'], win_count))
    
    for model_name, win_count in win_stats:
        win_rate = (win_count / total_wins * 100) if total_wins > 0 else 0
        print(f"    {model_name:<15}: {win_count:>4} 次胜出 ({win_rate:.1f}%)")
    
    # 平局统计
    cursor.execute("""
        SELECT COUNT(*) as tie_count
        FROM comparisons
        WHERE chosen_model = 'tie'
    """)
    tie_count = cursor.fetchone()['tie_count']
    
    total_comparisons = total_wins + tie_count
    tie_rate = (tie_count / total_comparisons * 100) if total_comparisons > 0 else 0
    print(f"    {'平局':<15}: {tie_count:>4} 次 ({tie_rate:.1f}%)")
    
    conn.close()


def show_category_progress():
    """显示类别进度"""
    print("\n📂 类别评测进度:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            p.category,
            COUNT(DISTINCT t.task_id) as total_tasks,
            COUNT(DISTINCT CASE WHEN t.completed = 1 THEN t.task_id END) as completed_tasks,
            SUM(t.current_ratings) as total_ratings
        FROM prompts p
        JOIN tasks t ON p.sample_id = t.sample_id
        GROUP BY p.category
        ORDER BY p.category
    """)
    
    print(f"  {'类别':<25} {'已完成':<8} {'总任务':<8} {'完成率':<10} {'已评次数':<10}")
    print(f"  {'-'*78}")
    
    for row in cursor.fetchall():
        category = row['category']
        total = row['total_tasks']
        completed = row['completed_tasks']
        ratings = row['total_ratings']
        percentage = (completed / total * 100) if total > 0 else 0
        print(f"  {category:<25} {completed:<8} {total:<8} {percentage:>6.1f}%    {ratings} 次")
    
    conn.close()


def show_time_estimate():
    """估算完成时间"""
    print("\n⏱️  完成时间估算:")
    print("-" * 80)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取已完成的评测数和时间范围
    cursor.execute("""
        SELECT 
            COUNT(*) as total_comparisons,
            MIN(rating_time) as first_rating,
            MAX(rating_time) as last_rating
        FROM comparisons
    """)
    
    row = cursor.fetchone()
    total_comparisons = row['total_comparisons']
    
    if total_comparisons > 0:
        from datetime import datetime
        first_time = datetime.fromisoformat(row['first_rating'])
        last_time = datetime.fromisoformat(row['last_rating'])
        time_span = (last_time - first_time).total_seconds()
        
        if time_span > 0:
            avg_time_per_comparison = time_span / total_comparisons
            
            # 获取剩余评测数
            cursor.execute("""
                SELECT 
                    SUM(CASE 
                        WHEN current_ratings = 0 THEN 3
                        WHEN current_ratings = 1 THEN 2
                        WHEN current_ratings = 2 THEN 1
                        ELSE 0
                    END) as remaining
                FROM tasks
            """)
            remaining = cursor.fetchone()['remaining']
            
            estimated_seconds = remaining * avg_time_per_comparison
            estimated_hours = estimated_seconds / 3600
            estimated_days = estimated_hours / 24
            
            print(f"  已完成评测: {total_comparisons} 次")
            print(f"  平均用时:   {avg_time_per_comparison:.1f} 秒/次")
            print(f"  剩余评测:   {remaining} 次")
            print(f"  预计还需:   {estimated_hours:.1f} 小时 ({estimated_days:.1f} 天)")
    else:
        print("  暂无数据，无法估算")
    
    conn.close()


def main():
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        print("   请先运行初始化脚本")
        return
    
    print("=" * 80)
    print("比较评测模式 - 详细进度报告（3人评测制）")
    print("=" * 80)
    
    show_task_rating_distribution()  # 新增：任务评测次数分布
    show_task_progress()
    show_judge_detailed_progress()   # 增强：更详细的评审员进度
    show_model_comparison()
    show_category_progress()
    show_time_estimate()             # 新增：完成时间估算
    
    print("\n" + "=" * 80)
    print("\n💡 提示: 运行 python get_links_compare.py 获取评审员访问链接")
    print("=" * 80)


if __name__ == "__main__":
    main()

