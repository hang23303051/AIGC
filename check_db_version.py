#!/usr/bin/env python3
"""快速检查数据库版本"""
import sqlite3

db_path = 'aiv_eval_v4.db'

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 检查是否有tasks表
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    has_tasks = cur.fetchone() is not None
    
    if has_tasks:
        print("✅ V2系统（3人评测制）")
        
        # 显示V2统计
        cur.execute("SELECT COUNT(*) FROM tasks")
        task_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=1")
        completed = cur.fetchone()[0]
        
        print(f"\n📊 任务统计:")
        print(f"  总任务数: {task_count}")
        print(f"  已完成: {completed}")
        print(f"  未完成: {task_count - completed}")
        
    else:
        print("❌ V1系统（所有人评测）")
        print("\n⚠️  需要执行迁移！")
        print("   运行: python scripts\\migrate_v1_to_v2.py")
    
    conn.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")

