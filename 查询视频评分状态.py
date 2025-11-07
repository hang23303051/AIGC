#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询指定视频的评分状态

用法：
  python 查询视频评分状态.py food_058_single cogvideo5b
"""
import sys
import sqlite3

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def query_video(sample_id, modelname):
    conn = sqlite3.connect('aiv_eval_v4.db')
    cur = conn.cursor()
    
    # 查找视频
    cur.execute('''
        SELECT id FROM videos 
        WHERE sample_id=? AND modelname=?
    ''', (sample_id, modelname))
    
    result = cur.fetchone()
    if not result:
        print(f"❌ 未找到视频: {sample_id} / {modelname}")
        conn.close()
        return
    
    video_id = result[0]
    
    print("="*80)
    print(f"  视频评分状态：{sample_id} / {modelname}")
    print("="*80)
    print(f"\nvideo_id: {video_id}")
    
    # 查询task信息
    cur.execute('''
        SELECT t.id, t.current_ratings, t.required_ratings, t.completed, t.completed_at
        FROM tasks t
        WHERE t.video_id = ?
    ''', (video_id,))
    
    task_info = cur.fetchone()
    if task_info:
        task_id, current_ratings, required_ratings, completed, completed_at = task_info
        print(f"\ntask_id: {task_id}")
        print(f"current_ratings: {current_ratings}")
        print(f"required_ratings: {required_ratings}")
        print(f"completed: {completed}")
        print(f"completed_at: {completed_at or 'N/A'}")
    else:
        print("\n❌ 未找到task记录")
        conn.close()
        return
    
    # 查询实际评分
    cur.execute('''
        SELECT r.id, r.judge_id, j.name, 
               r.score_semantic, r.score_motion, r.score_temporal, r.score_realism,
               r.created_at, r.submitted_at
        FROM ratings r
        JOIN judges j ON r.judge_id = j.id
        WHERE r.video_id = ?
        ORDER BY r.created_at
    ''', (video_id,))
    
    ratings = cur.fetchall()
    
    print(f"\n实际评分记录：{len(ratings)} 个")
    print("-"*80)
    
    if ratings:
        print(f"{'Rating ID':<12} {'Judge ID':<10} {'Judge':<15} {'语义':<6} {'运动':<6} {'时序':<6} {'真实':<6} {'创建时间':<20}")
        print("-"*80)
        for rating_id, judge_id, judge_name, sem, mot, tem, rea, created, submitted in ratings:
            created_str = str(created)[:19] if created else 'N/A'
            print(f"{rating_id:<12} {judge_id:<10} {judge_name:<15} {sem:<6} {mot:<6} {tem:<6} {rea:<6} {created_str:<20}")
    
    # 检查一致性
    print("\n" + "="*80)
    if len(ratings) == current_ratings:
        print("✅ 数据一致：实际评分数 = task.current_ratings")
    else:
        print(f"❌ 数据不一致：实际{len(ratings)}个评分，但task.current_ratings={current_ratings}")
    
    if current_ratings >= required_ratings and completed == 0:
        print(f"⚠️  已达到required_ratings（{required_ratings}），但未标记为completed")
    elif current_ratings >= required_ratings and completed == 1:
        print(f"✅ 已标记为completed（达到{required_ratings}次评分）")
    else:
        print(f"ℹ️  进行中：{current_ratings}/{required_ratings} 次评分")
    
    # 查询assignments
    cur.execute('''
        SELECT a.id, a.judge_id, j.name, a.finished, a.finished_at,
               (SELECT COUNT(*) FROM ratings r WHERE r.judge_id=a.judge_id AND r.video_id=?) as has_rating
        FROM assignments a
        JOIN judges j ON a.judge_id = j.id
        WHERE a.task_id = ?
        ORDER BY a.finished DESC, a.judge_id
    ''', (video_id, task_id))
    
    assignments = cur.fetchall()
    
    print(f"\nassignments：{len(assignments)} 个")
    print("-"*80)
    if assignments:
        print(f"{'Assign ID':<12} {'Judge ID':<10} {'Judge':<15} {'Finished':<10} {'Has Rating':<12}")
        print("-"*80)
        for assign_id, judge_id, judge_name, finished, finished_at, has_rating in assignments:
            finished_str = "✅ 是" if finished else "❌ 否"
            has_rating_str = "✅ 是" if has_rating else "❌ 否"
            print(f"{assign_id:<12} {judge_id:<10} {judge_name:<15} {finished_str:<10} {has_rating_str:<12}")
    
    print("="*80)
    conn.close()

def main():
    if len(sys.argv) != 3:
        print("用法：python 查询视频评分状态.py <sample_id> <modelname>")
        print("例如：python 查询视频评分状态.py food_058_single cogvideo5b")
        sys.exit(1)
    
    sample_id = sys.argv[1]
    modelname = sys.argv[2]
    
    query_video(sample_id, modelname)

if __name__ == "__main__":
    main()

