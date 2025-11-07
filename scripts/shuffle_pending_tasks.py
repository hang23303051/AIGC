#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机打散每个judge的待评测任务顺序
- 保持已完成任务（finished=1）不变
- 将未完成任务（finished=0）随机打散并重新排序
"""

import sqlite3
import random
import sys
import io

# Windows编码支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def shuffle_pending_tasks(db_path: str, seed: int = None):
    """
    随机打散每个judge的待评测任务
    
    Args:
        db_path: 数据库路径
        seed: 随机种子（默认使用系统随机）
    """
    if seed is None:
        seed = random.randint(1, 100000)
    
    print("=" * 80)
    print("  随机打散待评测任务")
    print("=" * 80)
    print(f"随机种子: {seed}")
    print()
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. 获取所有judge
    cur.execute("SELECT id, name FROM judges ORDER BY id")
    judges = cur.fetchall()
    
    print(f"共有 {len(judges)} 个评审员")
    print()
    
    # 2. 为每个judge随机打散未完成任务
    total_shuffled = 0
    
    for judge_id, judge_name in judges:
        # 2.1 获取该judge的已完成任务（finished=1）
        cur.execute("""
            SELECT id, display_order, task_id
            FROM assignments
            WHERE judge_id = ? AND finished = 1
            ORDER BY display_order
        """, (judge_id,))
        finished_assignments = cur.fetchall()
        
        # 2.2 获取该judge的未完成任务（finished=0）
        cur.execute("""
            SELECT id, display_order, task_id
            FROM assignments
            WHERE judge_id = ? AND finished = 0
            ORDER BY display_order
        """, (judge_id,))
        pending_assignments = cur.fetchall()
        
        if not pending_assignments:
            print(f"[{judge_id:2d}] {judge_name:15s} - 无待评测任务，跳过")
            continue
        
        # 2.3 找出最大的finished display_order
        if finished_assignments:
            max_finished_order = max(a[1] for a in finished_assignments)
        else:
            max_finished_order = -1
        
        # 2.4 随机打散未完成任务
        rnd = random.Random(f"{seed}-judge-{judge_id}")
        pending_ids = [a[0] for a in pending_assignments]
        rnd.shuffle(pending_ids)
        
        # 2.5 重新分配display_order（从max_finished_order+1开始）
        updates = []
        for new_order, assign_id in enumerate(pending_ids, start=max_finished_order + 1):
            updates.append((new_order, assign_id))
        
        # 2.6 批量更新数据库
        cur.executemany("""
            UPDATE assignments
            SET display_order = ?
            WHERE id = ?
        """, updates)
        
        conn.commit()
        
        print(f"[{judge_id:2d}] {judge_name:15s} - "
              f"已完成: {len(finished_assignments):3d}, "
              f"待评测: {len(pending_assignments):3d} (已打散)")
        
        total_shuffled += len(pending_assignments)
    
    print()
    print("=" * 80)
    print(f"✅ 完成！共打散 {total_shuffled} 个待评测任务")
    print("=" * 80)
    print()
    print("验证方法：")
    print("  1. 启动系统：.\\lan_start_with_monitor.ps1")
    print("  2. 访问任意judge链接")
    print("  3. 检查任务顺序是否已打散（同一参考视频的模型不再连续）")
    print()
    
    conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='随机打散每个judge的待评测任务')
    parser.add_argument('--db', default='aiv_eval_v4.db', help='数据库路径')
    parser.add_argument('--seed', type=int, default=None, help='随机种子（可选）')
    args = parser.parse_args()
    
    shuffle_pending_tasks(args.db, args.seed)


if __name__ == '__main__':
    main()

