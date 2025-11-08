#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 评分导出脚本
导出比较结果到CSV文件
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime

# 配置
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "aiv_compare_v1.db"
EXPORT_DIR = PROJECT_ROOT / "export_results_compare"


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def export_long_format():
    """导出长格式数据（每行一个评测记录）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.comparison_id,
            c.task_id,
            t.sample_id,
            p.category,
            p.prompt_text,
            t.model_a,
            t.model_b,
            c.judge_id,
            j.judge_name,
            c.chosen_model,
            c.comment,
            c.rating_time
        FROM comparisons c
        JOIN tasks t ON c.task_id = t.task_id
        JOIN prompts p ON t.sample_id = p.sample_id
        JOIN judges j ON c.judge_id = j.judge_id
        ORDER BY c.rating_time
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"comparisons_long_{timestamp}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            'comparison_id', 'task_id', 'sample_id', 'category', 'prompt_text',
            'model_a', 'model_b', 'judge_id', 'judge_name', 
            'chosen_model', 'comment', 'rating_time'
        ])
        
        for row in rows:
            writer.writerow([
                row['comparison_id'],
                row['task_id'],
                row['sample_id'],
                row['category'],
                row['prompt_text'],
                row['model_a'],
                row['model_b'],
                row['judge_id'],
                row['judge_name'],
                row['chosen_model'],
                row['comment'] or '',
                row['rating_time']
            ])
    
    print(f"  ✅ 长格式: {output_file.name}")
    return len(rows)


def export_task_summary():
    """导出任务汇总（每个任务的所有评测结果）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            t.task_id,
            t.sample_id,
            p.category,
            t.model_a,
            t.model_b,
            t.completed,
            t.current_ratings,
            GROUP_CONCAT(j.judge_name, '; ') as judges,
            GROUP_CONCAT(c.chosen_model, '; ') as choices,
            SUM(CASE WHEN c.chosen_model = t.model_a THEN 1 ELSE 0 END) as model_a_wins,
            SUM(CASE WHEN c.chosen_model = t.model_b THEN 1 ELSE 0 END) as model_b_wins,
            SUM(CASE WHEN c.chosen_model = 'tie' THEN 1 ELSE 0 END) as ties
        FROM tasks t
        JOIN prompts p ON t.sample_id = p.sample_id
        LEFT JOIN comparisons c ON t.task_id = c.task_id
        LEFT JOIN judges j ON c.judge_id = j.judge_id
        GROUP BY t.task_id
        ORDER BY t.sample_id, t.model_a, t.model_b
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"task_summary_{timestamp}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            'task_id', 'sample_id', 'category', 'model_a', 'model_b',
            'completed', 'current_ratings', 'judges', 'choices',
            'model_a_wins', 'model_b_wins', 'ties'
        ])
        
        for row in rows:
            writer.writerow([
                row['task_id'],
                row['sample_id'],
                row['category'],
                row['model_a'],
                row['model_b'],
                row['completed'],
                row['current_ratings'],
                row['judges'] or '',
                row['choices'] or '',
                row['model_a_wins'] or 0,
                row['model_b_wins'] or 0,
                row['ties'] or 0
            ])
    
    print(f"  ✅ 任务汇总: {output_file.name}")
    return len(rows)


def export_model_stats():
    """导出模型统计"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取所有模型
    cursor.execute("""
        SELECT DISTINCT model_name
        FROM videos
        ORDER BY model_name
    """)
    models = [row['model_name'] for row in cursor.fetchall()]
    
    # 计算每个模型的统计
    stats = []
    for model in models:
        cursor.execute("""
            SELECT COUNT(*) as win_count
            FROM comparisons
            WHERE chosen_model = ?
        """, (model,))
        win_count = cursor.fetchone()['win_count']
        
        cursor.execute("""
            SELECT COUNT(*) as total_tasks
            FROM tasks
            WHERE model_a = ? OR model_b = ?
        """, (model, model))
        total_tasks = cursor.fetchone()['total_tasks']
        
        cursor.execute("""
            SELECT COUNT(*) as completed_tasks
            FROM tasks
            WHERE (model_a = ? OR model_b = ?) AND completed = 1
        """, (model, model))
        completed_tasks = cursor.fetchone()['completed_tasks']
        
        stats.append({
            'model_name': model,
            'win_count': win_count,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'win_rate': (win_count / (completed_tasks * 3) * 100) if completed_tasks > 0 else 0
        })
    
    conn.close()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"model_stats_{timestamp}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'model_name', 'win_count', 'total_tasks', 'completed_tasks', 'win_rate'
        ])
        writer.writeheader()
        writer.writerows(stats)
    
    print(f"  ✅ 模型统计: {output_file.name}")
    return len(stats)


def export_progress_summary():
    """导出进度摘要"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = EXPORT_DIR / f"summary_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("比较评测模式 - 进度摘要\n")
        f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        # 任务统计
        cursor.execute("SELECT COUNT(*) as total FROM tasks")
        total_tasks = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as completed FROM tasks WHERE completed = 1")
        completed_tasks = cursor.fetchone()['completed']
        
        cursor.execute("SELECT COUNT(*) as done FROM comparisons")
        done_comparisons = cursor.fetchone()['done']
        
        f.write("📊 任务完成情况:\n")
        f.write(f"  总任务数: {total_tasks}\n")
        f.write(f"  已完成: {completed_tasks}\n")
        f.write(f"  完成率: {completed_tasks/total_tasks*100:.2f}%\n")
        f.write(f"  已完成评测数: {done_comparisons}\n")
        f.write(f"  需要评测总数: {total_tasks * 3}\n\n")
        
        # 评审员统计
        cursor.execute("""
            SELECT j.judge_name, COUNT(c.comparison_id) as completed
            FROM judges j
            LEFT JOIN comparisons c ON j.judge_id = c.judge_id
            GROUP BY j.judge_id, j.judge_name
            ORDER BY j.judge_name
        """)
        
        f.write("👥 评审员进度:\n")
        for row in cursor.fetchall():
            f.write(f"  {row['judge_name']}: {row['completed']}\n")
        f.write("\n")
        
        # 模型统计
        cursor.execute("""
            SELECT chosen_model, COUNT(*) as count
            FROM comparisons
            GROUP BY chosen_model
            ORDER BY count DESC
        """)
        
        f.write("🤖 模型选择统计:\n")
        for row in cursor.fetchall():
            f.write(f"  {row['chosen_model']}: {row['count']}\n")
    
    conn.close()
    
    print(f"  ✅ 进度摘要: {output_file.name}")


def main():
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        return
    
    # 确保导出目录存在
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("比较评测模式 - 数据导出")
    print("="*80)
    print(f"\n导出目录: {EXPORT_DIR}")
    print("\n开始导出...")
    
    # 导出各种格式
    long_count = export_long_format()
    task_count = export_task_summary()
    model_count = export_model_stats()
    export_progress_summary()
    
    print("\n" + "="*80)
    print("✅ 导出完成！")
    print("="*80)
    print(f"\n统计:")
    print(f"  评测记录: {long_count} 条")
    print(f"  任务数: {task_count} 个")
    print(f"  模型数: {model_count} 个")


if __name__ == "__main__":
    main()

