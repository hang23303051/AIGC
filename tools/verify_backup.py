#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证备份完整性"""
import sys
import sqlite3

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def verify_backup(db_path):
    """验证备份数据库"""
    print(f"\n验证备份：{db_path}")
    print("="*80)
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # 1. 检查表
        print("\n1. 检查表结构...")
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        
        required_tables = ['judges', 'prompts', 'videos', 'ratings', 'tasks', 'assignments']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"   ❌ 缺少表：{missing_tables}")
            return False
        else:
            print(f"   ✅ 所有必需的表都存在：{required_tables}")
        
        # 2. 检查数据量
        print("\n2. 检查数据量...")
        cur.execute("SELECT COUNT(*) FROM judges")
        judges_count = cur.fetchone()[0]
        print(f"   - Judges: {judges_count}")
        
        cur.execute("SELECT COUNT(*) FROM prompts")
        prompts_count = cur.fetchone()[0]
        print(f"   - Prompts: {prompts_count}")
        
        cur.execute("SELECT COUNT(*) FROM videos")
        videos_count = cur.fetchone()[0]
        print(f"   - Videos: {videos_count}")
        
        cur.execute("SELECT COUNT(*) FROM ratings")
        ratings_count = cur.fetchone()[0]
        print(f"   - Ratings: {ratings_count}")
        
        cur.execute("SELECT COUNT(*) FROM tasks")
        tasks_count = cur.fetchone()[0]
        print(f"   - Tasks: {tasks_count}")
        
        cur.execute("SELECT COUNT(*) FROM assignments")
        assignments_count = cur.fetchone()[0]
        print(f"   - Assignments: {assignments_count}")
        
        if ratings_count == 0:
            print("   ❌ 没有评分记录")
            return False
        
        # 3. 检查UNIQUE约束
        print("\n3. 检查UNIQUE约束...")
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ratings'")
        ratings_sql = cur.fetchone()[0]
        
        if "UNIQUE" in ratings_sql and "judge_id" in ratings_sql and "video_id" in ratings_sql:
            print("   ✅ ratings表包含UNIQUE(judge_id, video_id)约束")
        else:
            print("   ❌ ratings表缺少UNIQUE约束")
            return False
        
        # 4. 检查触发器
        print("\n4. 检查触发器...")
        cur.execute("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")
        triggers = [row[0] for row in cur.fetchall()]
        
        required_triggers = ['update_task_on_rating_insert', 'cleanup_assignments_on_task_complete']
        missing_triggers = [t for t in required_triggers if t not in triggers]
        
        if missing_triggers:
            print(f"   ⚠️  缺少触发器：{missing_triggers}")
        else:
            print(f"   ✅ 所有触发器都存在：{required_triggers}")
        
        # 5. 检查字段
        print("\n5. 检查关键字段...")
        cur.execute("PRAGMA table_info(ratings)")
        ratings_columns = [row[1] for row in cur.fetchall()]
        
        if 'submitted_at' in ratings_columns:
            print("   ✅ ratings表包含submitted_at字段")
        else:
            print("   ⚠️  ratings表缺少submitted_at字段")
        
        cur.execute("PRAGMA table_info(assignments)")
        assignments_columns = [row[1] for row in cur.fetchall()]
        
        required_assignment_cols = ['judge_id', 'task_id', 'display_order', 'finished']
        missing_cols = [c for c in required_assignment_cols if c not in assignments_columns]
        
        if missing_cols:
            print(f"   ❌ assignments表缺少字段：{missing_cols}")
            return False
        else:
            print(f"   ✅ assignments表结构正确")
        
        # 6. 检查数据一致性
        print("\n6. 检查数据一致性...")
        cur.execute("""
            SELECT COUNT(*) FROM tasks t
            WHERE t.current_ratings != (
                SELECT COUNT(DISTINCT judge_id) FROM ratings WHERE video_id = t.video_id
            )
        """)
        inconsistent_tasks = cur.fetchone()[0]
        
        if inconsistent_tasks > 0:
            print(f"   ⚠️  有 {inconsistent_tasks} 个tasks的current_ratings不一致")
        else:
            print(f"   ✅ 所有tasks的current_ratings一致")
        
        conn.close()
        
        print("\n" + "="*80)
        print("✅ 备份验证通过！备份可以安全使用。")
        return True
        
    except Exception as e:
        print(f"\n❌ 验证失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    backup_path = "backup/aiv_eval_v4_v2_clean_restored_20251101.db"
    
    print("="*80)
    print("  备份完整性验证")
    print("="*80)
    
    success = verify_backup(backup_path)
    
    if success:
        print("\n✅ 备份完整且可用")
        sys.exit(0)
    else:
        print("\n❌ 备份验证失败，请检查")
        sys.exit(1)

if __name__ == "__main__":
    main()

