#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从V1备份恢复并迁移到V2，应用所有修复

步骤：
1. 备份当前数据库
2. 恢复V1备份
3. 迁移到V2系统
4. 应用所有修复（UNIQUE约束、触发器）
"""
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def backup_current_db(db_path):
    """备份当前数据库"""
    if not Path(db_path).exists():
        print(f"ℹ️  当前数据库不存在，跳过备份")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"backup/aiv_eval_v4_before_restore_{timestamp}.db"
    
    print(f"📦 备份当前数据库...")
    shutil.copy2(db_path, backup_path)
    print(f"   ✓ 备份到: {backup_path}")

def migrate_to_v2(db_path):
    """迁移V1到V2"""
    print("\n🔄 迁移V1到V2系统...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # 1. 创建tasks表
        print("   1. 创建tasks表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT NOT NULL,
                video_id INTEGER NOT NULL,
                required_ratings INTEGER DEFAULT 3,
                current_ratings INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                UNIQUE(prompt_id, video_id),
                FOREIGN KEY (prompt_id) REFERENCES prompts(id),
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """)
        
        # 2. 从videos创建tasks
        print("   2. 创建tasks记录...")
        cur.execute("""
            INSERT OR IGNORE INTO tasks (prompt_id, video_id, required_ratings, current_ratings, completed)
            SELECT prompt_id, id, 3, 0, 0
            FROM videos
        """)
        tasks_created = cur.rowcount
        print(f"   ✓ 创建 {tasks_created} 个tasks")
        
        # 3. 重建assignments表（V1结构不兼容，需要重建）
        print("   3. 重建assignments表...")
        
        # 保存V1的已完成assignments信息
        cur.execute("""
            SELECT judge_id, prompt_id
            FROM assignments
            WHERE finished = 1
        """)
        finished_v1 = cur.fetchall()
        print(f"   ℹ️  保存 {len(finished_v1)} 条已完成assignments信息")
        
        # 删除旧表，创建新表
        cur.execute("DROP TABLE IF EXISTS assignments")
        cur.execute("""
            CREATE TABLE assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                judge_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                display_order INTEGER NOT NULL,
                finished INTEGER DEFAULT 0,
                finished_at TIMESTAMP,
                FOREIGN KEY (judge_id) REFERENCES judges(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                UNIQUE(judge_id, task_id)
            )
        """)
        print("   ✓ 创建新的assignments表")
        
        # 4. 为每个task创建assignments
        print("   4. 创建assignments...")
        
        # 获取所有judges
        cur.execute("SELECT id FROM judges ORDER BY id")
        judges = [row[0] for row in cur.fetchall()]
        
        # 获取所有tasks，按prompt_id排序
        cur.execute("""
            SELECT t.id, t.video_id, t.prompt_id, v.modelname
            FROM tasks t
            JOIN videos v ON t.video_id = v.id
            ORDER BY t.prompt_id, v.modelname
        """)
        tasks = cur.fetchall()
        
        assignments_created = 0
        display_orders = {judge_id: 0 for judge_id in judges}  # 每个judge的display_order计数
        
        for task_id, video_id, prompt_id, modelname in tasks:
            for judge_id in judges:
                # 为每个judge创建assignment
                cur.execute("""
                    INSERT INTO assignments (judge_id, task_id, display_order, finished)
                    VALUES (?, ?, ?, 0)
                """, (judge_id, task_id, display_orders[judge_id]))
                
                display_orders[judge_id] += 1
                assignments_created += 1
        
        print(f"   ✓ 创建 {assignments_created} 个assignments")
        
        # 5. 更新current_ratings和completed状态
        print("   5. 更新task统计...")
        cur.execute("""
            UPDATE tasks
            SET current_ratings = (
                SELECT COUNT(DISTINCT judge_id)
                FROM ratings
                WHERE ratings.video_id = tasks.video_id
            )
        """)
        
        cur.execute("""
            UPDATE tasks
            SET completed = 1,
                completed_at = CURRENT_TIMESTAMP
            WHERE current_ratings >= required_ratings
        """)
        completed = cur.rowcount
        print(f"   ✓ 标记 {completed} 个tasks为completed")
        
        # 6. 更新已有评分的assignments为finished=1
        print("   6. 更新assignments状态...")
        cur.execute("""
            UPDATE assignments
            SET finished = 1,
                finished_at = CURRENT_TIMESTAMP
            WHERE EXISTS (
                SELECT 1 FROM ratings r
                JOIN tasks t ON t.id = assignments.task_id
                WHERE r.judge_id = assignments.judge_id
                  AND r.video_id = t.video_id
            )
            AND finished = 0
        """)
        updated = cur.rowcount
        print(f"   ✓ 更新 {updated} 个assignments为finished")
        
        conn.commit()
        print("   ✅ V2迁移成功")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 迁移失败：{e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def apply_unique_constraint(db_path):
    """应用UNIQUE约束"""
    print("\n🔧 应用UNIQUE约束...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # 检查是否已有UNIQUE约束
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ratings'")
        sql = cur.fetchone()[0]
        if "UNIQUE" in sql and "judge_id" in sql and "video_id" in sql:
            print("   ℹ️  UNIQUE约束已存在，跳过")
            conn.close()
            return True
        
        # 1. 删除依赖视图
        print("   1. 删除依赖视图...")
        cur.execute("DROP VIEW IF EXISTS judge_workload_stats")
        cur.execute("DROP VIEW IF EXISTS task_completion_stats")
        cur.execute("DROP VIEW IF EXISTS task_details")
        
        # 2. 创建新表
        print("   2. 创建新的ratings表...")
        cur.execute("""
            CREATE TABLE ratings_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                judge_id INTEGER NOT NULL,
                prompt_id TEXT,
                video_id INTEGER NOT NULL,
                modelname TEXT,
                sample_id TEXT,
                score_semantic INTEGER NOT NULL CHECK(score_semantic BETWEEN 1 AND 5),
                score_motion INTEGER NOT NULL CHECK(score_motion BETWEEN 1 AND 5),
                score_temporal INTEGER NOT NULL CHECK(score_temporal BETWEEN 1 AND 5),
                score_realism INTEGER NOT NULL CHECK(score_realism BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                submitted_at TIMESTAMP,
                FOREIGN KEY (judge_id) REFERENCES judges(id),
                FOREIGN KEY (prompt_id) REFERENCES prompts(id),
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
                UNIQUE(judge_id, video_id)
            )
        """)
        
        # 3. 复制数据（去重）
        print("   3. 复制数据（去重）...")
        cur.execute("""
            INSERT INTO ratings_new 
            SELECT id, judge_id, prompt_id, video_id, modelname, sample_id,
                   score_semantic, score_motion, score_temporal, score_realism,
                   created_at, submitted_at
            FROM ratings
            WHERE id IN (
                SELECT MAX(id) 
                FROM ratings 
                GROUP BY judge_id, video_id
            )
        """)
        
        rows_copied = cur.rowcount
        print(f"   ✓ 复制 {rows_copied} 条记录")
        
        # 4. 删除旧表，重命名新表
        print("   4. 替换表...")
        cur.execute("DROP TABLE ratings")
        cur.execute("ALTER TABLE ratings_new RENAME TO ratings")
        
        # 5. 重建索引
        print("   5. 重建索引...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ratings_judge ON ratings(judge_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ratings_video ON ratings(video_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ratings_sample_model ON ratings(sample_id, modelname)")
        
        # 6. 重建视图
        print("   6. 重建视图...")
        cur.execute("""
            CREATE VIEW task_completion_stats AS
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) as completed_tasks,
                SUM(current_ratings) as total_ratings_done,
                COUNT(*) * 3 as total_ratings_needed
            FROM tasks
        """)
        
        cur.execute("""
            CREATE VIEW judge_workload_stats AS
            SELECT 
                j.id,
                j.name,
                COUNT(DISTINCT a.id) as total_assignments,
                SUM(CASE WHEN a.finished=1 THEN 1 ELSE 0 END) as finished_assignments,
                SUM(CASE WHEN a.finished=0 AND t.completed=0 THEN 1 ELSE 0 END) as pending_assignments
            FROM judges j
            LEFT JOIN assignments a ON a.judge_id = j.id
            LEFT JOIN tasks t ON a.task_id = t.id
            GROUP BY j.id, j.name
        """)
        
        cur.execute("""
            CREATE VIEW task_details AS
            SELECT 
                t.id as task_id,
                t.prompt_id,
                t.video_id,
                t.current_ratings,
                t.required_ratings,
                t.completed,
                p.text as prompt_text,
                v.modelname,
                v.sample_id
            FROM tasks t
            JOIN prompts p ON t.prompt_id = p.id
            JOIN videos v ON t.video_id = v.id
        """)
        
        conn.commit()
        print("   ✅ UNIQUE约束应用成功")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 失败：{e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def fix_triggers(db_path):
    """修复触发器"""
    print("\n🔧 修复触发器...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # 1. 删除旧触发器
        print("   1. 删除旧触发器...")
        cur.execute("DROP TRIGGER IF EXISTS update_task_on_rating_insert")
        cur.execute("DROP TRIGGER IF EXISTS cleanup_assignments_on_task_complete")
        
        # 2. 创建新触发器
        print("   2. 创建新触发器...")
        
        # 触发器1：当插入rating时更新task状态
        cur.execute("""
            CREATE TRIGGER update_task_on_rating_insert
            AFTER INSERT ON ratings
            FOR EACH ROW
            BEGIN
                UPDATE tasks 
                SET current_ratings = (
                    SELECT COUNT(DISTINCT judge_id) 
                    FROM ratings 
                    WHERE video_id = NEW.video_id
                )
                WHERE video_id = NEW.video_id;
                
                UPDATE tasks
                SET completed = 1,
                    completed_at = CURRENT_TIMESTAMP
                WHERE video_id = NEW.video_id
                  AND current_ratings >= required_ratings
                  AND completed = 0;
            END;
        """)
        
        # 触发器2：当task完成时删除未完成的assignments（但保留有rating的）
        cur.execute("""
            CREATE TRIGGER cleanup_assignments_on_task_complete
            AFTER UPDATE OF completed ON tasks
            FOR EACH ROW
            WHEN NEW.completed = 1 AND OLD.completed = 0
            BEGIN
                DELETE FROM assignments
                WHERE task_id = NEW.id
                  AND finished = 0
                  AND NOT EXISTS (
                    SELECT 1 FROM ratings 
                    WHERE ratings.judge_id = assignments.judge_id 
                    AND ratings.video_id = NEW.video_id
                  );
            END;
        """)
        
        conn.commit()
        print("   ✅ 触发器修复成功")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 失败：{e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def main():
    print("="*80)
    print("  从V1备份恢复并迁移到V2")
    print("="*80)
    
    backup_db = "backup/aiv_eval_v4_v1_backup.db"
    target_db = "aiv_eval_v4.db"
    
    # 检查备份文件
    if not Path(backup_db).exists():
        print(f"\n❌ 备份文件不存在: {backup_db}")
        sys.exit(1)
    
    print(f"\n📂 备份文件: {backup_db}")
    
    # 备份当前数据库
    backup_current_db(target_db)
    
    # 恢复备份
    print(f"\n🔄 恢复V1备份...")
    shutil.copy2(backup_db, target_db)
    print(f"   ✓ 恢复到: {target_db}")
    
    # 迁移到V2
    if not migrate_to_v2(target_db):
        print("\n❌ 迁移失败，停止")
        sys.exit(1)
    
    # 应用UNIQUE约束
    if not apply_unique_constraint(target_db):
        print("\n❌ 应用UNIQUE约束失败，停止")
        sys.exit(1)
    
    # 修复触发器
    if not fix_triggers(target_db):
        print("\n❌ 修复触发器失败，停止")
        sys.exit(1)
    
    # 显示统计
    print(f"\n📊 数据库统计:")
    conn = sqlite3.connect(target_db)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM tasks WHERE completed=1")
    completed_tasks = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM ratings")
    total_ratings = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM judges")
    total_judges = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM assignments WHERE finished=1")
    finished_assignments = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM assignments WHERE finished=0")
    pending_assignments = cur.fetchone()[0]
    
    print(f"   - 总tasks: {total_tasks}")
    print(f"   - 已完成tasks: {completed_tasks}")
    print(f"   - 未完成tasks: {total_tasks - completed_tasks}")
    print(f"   - 总评分: {total_ratings}")
    print(f"   - 评审员: {total_judges}")
    print(f"   - 已完成assignments: {finished_assignments}")
    print(f"   - 待做assignments: {pending_assignments}")
    
    conn.close()
    
    print("\n" + "="*80)
    print("  ✅ 恢复完成！")
    print("="*80)
    print("\n下一步:")
    print("  1. 重启服务: .\\lan_start_with_monitor.ps1")
    print("  2. 检查进度: D:\\miniconda3\\envs\\learn\\python.exe check_progress.py")
    print("  3. 开始评测")
    print("="*80)

if __name__ == "__main__":
    main()

