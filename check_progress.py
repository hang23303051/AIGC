#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看评测进度（基于V2系统：每任务3人评）"""
import sqlite3
import sys

# Windows编码支持
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    db_path = 'aiv_eval_v4.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        print("=" * 70)
        print("  评测进度总览（V2系统：每任务需3人评测）")
        print("=" * 70)
        
        # 检查是否有tasks表（V2系统）
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        has_tasks_table = cur.fetchone() is not None
        
        if has_tasks_table:
            # V2系统：基于tasks表统计
            cur.execute('SELECT COUNT(*) FROM tasks')
            total_tasks = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM tasks WHERE completed=1')
            completed_tasks = cur.fetchone()[0]
            
            cur.execute('SELECT SUM(current_ratings) FROM tasks')
            total_ratings_done = cur.fetchone()[0] or 0
            
            total_ratings_needed = total_tasks * 3
            
            progress_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            rating_pct = (total_ratings_done / total_ratings_needed * 100) if total_ratings_needed > 0 else 0
            
            print(f"\n📊 任务完成情况:")
            print(f"  总任务数: {total_tasks}")
            print(f"  已完成（被评3次）: {completed_tasks}")
            print(f"  未完成: {total_tasks - completed_tasks}")
            print(f"  完成率: {progress_pct:.2f}%")
            
            print(f"\n📝 评分完成情况:")
            print(f"  需要评分总数: {total_ratings_needed} (={total_tasks}×3)")
            print(f"  已完成评分数: {total_ratings_done}")
            print(f"  还需评分数: {total_ratings_needed - total_ratings_done}")
            print(f"  评分进度: {rating_pct:.2f}%")
        else:
            # V1系统：传统统计
            cur.execute('SELECT COUNT(*) FROM assignments')
            total_tasks = cur.fetchone()[0]
            
            cur.execute('SELECT COUNT(*) FROM assignments WHERE finished=1')
            finished_tasks = cur.fetchone()[0]
            
            progress_pct = (finished_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            print(f"\n总任务数: {total_tasks}")
            print(f"已完成: {finished_tasks}")
            print(f"未完成: {total_tasks - finished_tasks}")
            print(f"完成率: {progress_pct:.2f}%")
        
        # 每个评审员的进度
        print("\n" + "=" * 70)
        print("  各评审员进度")
        print("=" * 70)
        
        if has_tasks_table:
            # V2系统：显示每个judge的未完成任务数（task还未被评3次的）
            print(f"{'评审员':<15} {'已完成':<10} {'待做':<10} {'总':<10} {'进度':<10}")
            print("-" * 70)
            
            cur.execute('''
                SELECT j.name, j.id,
                       SUM(CASE WHEN a.finished=1 THEN 1 ELSE 0 END) as done,
                       SUM(CASE WHEN a.finished=0 AND t.completed=0 THEN 1 ELSE 0 END) as pending
                FROM judges j
                LEFT JOIN assignments a ON a.judge_id = j.id
                LEFT JOIN tasks t ON a.task_id = t.id
                GROUP BY j.id, j.name
                ORDER BY j.name
            ''')
            
            for name, jid, done, pending in cur.fetchall():
                done = done or 0
                pending = pending or 0
                total = done + pending
                pct = (done / total * 100) if total > 0 else 0
                print(f"{name:<15} {done:<10} {pending:<10} {total:<10} {pct:>6.2f}%")
        else:
            # V1系统
            print(f"{'评审员':<15} {'已完成':<10} {'总任务':<10} {'进度':<10}")
            print("-" * 70)
            
            cur.execute('''
                SELECT j.name, j.id,
                       COUNT(a.id) as total,
                       SUM(CASE WHEN a.finished=1 THEN 1 ELSE 0 END) as done
                FROM judges j
                LEFT JOIN assignments a ON a.judge_id = j.id
                GROUP BY j.id, j.name
                ORDER BY j.name
            ''')
            
            for name, jid, total, done in cur.fetchall():
                done = done or 0
                pct = (done / total * 100) if total > 0 else 0
                print(f"{name:<15} {done:<10} {total:<10} {pct:>6.2f}%")
        
        # 评分统计
        print("\n" + "=" * 70)
        print("  评分统计")
        print("=" * 70)
        
        cur.execute('SELECT COUNT(*) FROM ratings')
        total_ratings = cur.fetchone()[0]
        print(f"\n总评分记录数: {total_ratings}")
        
        # 按模型统计
        cur.execute('''
            SELECT modelname, COUNT(*) as cnt
            FROM ratings
            WHERE modelname IS NOT NULL
            GROUP BY modelname
            ORDER BY modelname
        ''')
        
        print(f"\n各模型评分数:")
        for model, cnt in cur.fetchall():
            print(f"  {model:<20} {cnt:>5} 个评分")
        
        # 平均分
        print(f"\n各维度平均分:")
        cur.execute('''
            SELECT 
                AVG(score_semantic) as avg_semantic,
                AVG(score_motion) as avg_motion,
                AVG(score_temporal) as avg_temporal,
                AVG(score_realism) as avg_realism
            FROM ratings
        ''')
        row = cur.fetchone()
        if row and row[0]:
            print(f"  基本语义对齐: {row[0]:.2f}")
            print(f"  运动:         {row[1]:.2f}")
            print(f"  事件时序:     {row[2]:.2f}")
            print(f"  世界知识:     {row[3]:.2f}")
        
        if has_tasks_table:
            # V2额外统计：任务完成分布
            print(f"\n📈 任务评分次数分布:")
            cur.execute('''
                SELECT current_ratings, COUNT(*) as cnt
                FROM tasks
                GROUP BY current_ratings
                ORDER BY current_ratings
            ''')
            for ratings, cnt in cur.fetchall():
                status = "✓ 已完成" if ratings >= 3 else f"进行中"
                print(f"  被评{ratings}次: {cnt:>5} 个任务 {status}")
        
        print("\n" + "=" * 70)
        
        conn.close()
        
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

