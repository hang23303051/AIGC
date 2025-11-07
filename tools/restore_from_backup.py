#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从备份恢复数据库并应用所有必要的修复

步骤：
1. 备份当前数据库
2. 检查备份数据库的结构
3. 恢复备份数据库
4. 应用所有数据库修复
"""
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

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

def check_db_structure(db_path):
    """检查数据库结构"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 检查是否有tasks表（V2系统）
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    has_tasks = cur.fetchone() is not None
    
    # 检查ratings表是否有UNIQUE约束
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ratings'")
    ratings_sql = cur.fetchone()
    has_unique = "UNIQUE" in ratings_sql[0] if ratings_sql else False
    
    # 检查触发器
    cur.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='update_task_on_rating_insert'")
    trigger_sql = cur.fetchone()
    has_trigger = trigger_sql is not None
    
    conn.close()
    
    return {
        'has_tasks': has_tasks,
        'has_unique': has_unique,
        'has_trigger': has_trigger
    }

def apply_unique_constraint(db_path):
    """应用UNIQUE约束"""
    print("\n🔧 应用UNIQUE约束...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
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
        print("   3. 复制数据...")
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
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 失败：{e}")
        raise
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
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 失败：{e}")
        raise
    finally:
        conn.close()

def recalculate_task_stats(db_path):
    """重新计算所有task的统计数据"""
    print("\n🔧 重新计算task统计...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # 更新所有task的current_ratings
        cur.execute("""
            UPDATE tasks
            SET current_ratings = (
                SELECT COUNT(DISTINCT judge_id)
                FROM ratings
                WHERE ratings.video_id = tasks.video_id
            )
        """)
        
        updated = cur.rowcount
        print(f"   ✓ 更新 {updated} 个tasks的current_ratings")
        
        # 更新completed状态
        cur.execute("""
            UPDATE tasks
            SET completed = 1,
                completed_at = CURRENT_TIMESTAMP
            WHERE current_ratings >= required_ratings
              AND completed = 0
        """)
        
        completed = cur.rowcount
        print(f"   ✓ 标记 {completed} 个tasks为completed")
        
        conn.commit()
        print("   ✅ 统计重新计算成功")
        
    except Exception as e:
        conn.rollback()
        print(f"   ❌ 失败：{e}")
        raise
    finally:
        conn.close()

def main():
    print("="*80)
    print("  从备份恢复数据库")
    print("="*80)
    
    backup_db = "backup/aiv_eval_v4_v1_backup.db"
    target_db = "aiv_eval_v4.db"
    
    # 检查备份文件
    if not Path(backup_db).exists():
        print(f"\n❌ 备份文件不存在: {backup_db}")
        sys.exit(1)
    
    print(f"\n📂 备份文件: {backup_db}")
    
    # 检查备份数据库的结构
    print(f"\n🔍 检查备份数据库结构...")
    backup_info = check_db_structure(backup_db)
    print(f"   - tasks表: {'✅ 存在' if backup_info['has_tasks'] else '❌ 不存在'}")
    print(f"   - UNIQUE约束: {'✅ 存在' if backup_info['has_unique'] else '❌ 不存在'}")
    print(f"   - 触发器: {'✅ 存在' if backup_info['has_trigger'] else '❌ 不存在'}")
    
    if not backup_info['has_tasks']:
        print(f"\n❌ 备份数据库是V1结构，需要先迁移到V2")
        print(f"   请先运行迁移脚本")
        sys.exit(1)
    
    # 备份当前数据库
    backup_current_db(target_db)
    
    # 恢复备份
    print(f"\n🔄 恢复备份数据库...")
    shutil.copy2(backup_db, target_db)
    print(f"   ✓ 恢复到: {target_db}")
    
    # 检查恢复后的数据库
    print(f"\n🔍 检查恢复后的数据库...")
    current_info = check_db_structure(target_db)
    
    # 应用必要的修复
    needs_fix = []
    if not current_info['has_unique']:
        needs_fix.append("UNIQUE约束")
    if not current_info['has_trigger']:
        needs_fix.append("触发器")
    
    if needs_fix:
        print(f"\n⚠️  需要应用以下修复: {', '.join(needs_fix)}")
        
        if not current_info['has_unique']:
            apply_unique_constraint(target_db)
        
        if not current_info['has_trigger']:
            fix_triggers(target_db)
        
        # 重新计算统计
        recalculate_task_stats(target_db)
    else:
        print(f"\n✅ 数据库结构完整，无需修复")
    
    # 验证最终状态
    print(f"\n🔍 验证最终状态...")
    final_info = check_db_structure(target_db)
    print(f"   - tasks表: {'✅ 存在' if final_info['has_tasks'] else '❌ 不存在'}")
    print(f"   - UNIQUE约束: {'✅ 存在' if final_info['has_unique'] else '❌ 不存在'}")
    print(f"   - 触发器: {'✅ 存在' if final_info['has_trigger'] else '❌ 不存在'}")
    
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
    
    print(f"   - 总tasks: {total_tasks}")
    print(f"   - 已完成: {completed_tasks}")
    print(f"   - 总评分: {total_ratings}")
    print(f"   - 评审员: {total_judges}")
    
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

