import argparse, sqlite3, csv, json, secrets, random, sys

def connect(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def ensure_schema(conn, schema_path):
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

def reset_all(conn):
    cur = conn.cursor()
    cur.execute("DELETE FROM ratings")
    cur.execute("DELETE FROM assignments")
    
    # 检查是否有tasks表（V2系统）
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    if cur.fetchone():
        cur.execute("DELETE FROM tasks")
    
    cur.execute("DELETE FROM videos")
    cur.execute("DELETE FROM prompts")
    cur.execute("DELETE FROM judges")
    conn.commit()

def read_csv(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader]
        headers = set([h.strip() for h in reader.fieldnames])
    required = {"prompt_id","prompt_text","ref_path","variant","gen_path"}
    missing = required - headers
    if missing:
        print(f"[ERROR] CSV 缺少列 {missing}. 需要列: {sorted(required)}")
        sys.exit(1)
    return rows

def upsert_prompts_and_videos(conn, rows):
    cur = conn.cursor()
    prompts_seen = set()
    for r in rows:
        pid = str(r["prompt_id"]).strip()
        text = r["prompt_text"]
        ref = r["ref_path"]
        v = int(r["variant"])
        path = r["gen_path"]
        # derive modelname from gen_path filename if possible
        modelname = None
        try:
            import os
            base = os.path.basename(path)
            modelname = os.path.splitext(base)[0]
        except Exception:
            modelname = None
        if pid not in prompts_seen:
            cur.execute("INSERT OR REPLACE INTO prompts(id, text, ref_path, sample_id) VALUES(?,?,?,?)", (pid, text, ref, pid))
            cur.execute("DELETE FROM videos WHERE prompt_id=?", (pid,))
            prompts_seen.add(pid)
        cur.execute("INSERT OR REPLACE INTO videos(prompt_id, variant_index, path, modelname, sample_id) VALUES(?,?,?,?,?)", (pid, v, path, modelname, pid))
    conn.commit()

def create_judges(conn, n):
    cur = conn.cursor(); toks = []
    for i in range(n):
        token = secrets.token_urlsafe(10)
        name = f"Judge-{i+1:02d}"
        cur.execute("INSERT INTO judges(name, token) VALUES(?,?)", (name, token))
        toks.append((cur.lastrowid, name, token))
    conn.commit(); return toks

def get_prompt_videos(conn, prompt_id):
    cur = conn.cursor()
    cur.execute("SELECT id FROM videos WHERE prompt_id=? ORDER BY variant_index", (prompt_id,))
    return [r[0] for r in cur.fetchall()]

def create_assignments(conn, seed=42):
    """
    V2逻辑：每任务需3人评
    1. 为每个video创建一个task
    2. 为每个judge分配所有tasks（顺序随机）
    """
    cur = conn.cursor()
    
    # 检查是否有tasks表（V2系统）
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    has_tasks_table = cur.fetchone() is not None
    
    cur.execute("SELECT id FROM judges"); judges = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM prompts ORDER BY id"); prompts = [r[0] for r in cur.fetchall()]
    
    if has_tasks_table:
        # V2系统：创建tasks，然后为所有judge分配（顺序随机）
        print("[INFO] 使用V2系统（每任务3人评）")
        
        # 1. 创建tasks（每个video一个task）
        tasks_created = 0
        for p in prompts:
            vids = get_prompt_videos(conn, p)
            if not vids:
                print(f"[WARN] Prompt {p} 没有视频，跳过")
                continue
            
            for vid in vids:
                cur.execute("""
                    INSERT INTO tasks (prompt_id, video_id, required_ratings, current_ratings, completed)
                    VALUES (?, ?, 3, 0, 0)
                """, (p, vid))
                tasks_created += 1
        
        conn.commit()
        print(f"[OK] 创建 {tasks_created} 个tasks")
        
        # 2. 获取所有task_ids
        cur.execute("SELECT id FROM tasks ORDER BY id")
        all_task_ids = [r[0] for r in cur.fetchall()]
        
        # 3. 为每个judge分配所有tasks（顺序随机）
        assignments_created = 0
        for j in judges:
            # 为每个judge随机打乱任务顺序
            rnd = random.Random(f"{seed}-judge-{j}")
            task_order = all_task_ids.copy()
            rnd.shuffle(task_order)
            
            # 创建assignments
            for display_order, task_id in enumerate(task_order):
                cur.execute("""
                    INSERT INTO assignments (judge_id, task_id, display_order, finished)
                    VALUES (?, ?, ?, 0)
                """, (j, task_id, display_order))
                assignments_created += 1
        
        conn.commit()
        print(f"[OK] 为 {len(judges)} 个judge创建 {assignments_created} 个assignments")
        print(f"     = {len(all_task_ids)} tasks × {len(judges)} judges")
        print(f"[INFO] 每个任务需要3个评审员评测，完成后自动从所有人列表中移除")
        
        return len(judges), len(prompts), assignments_created
    
    else:
        # V1系统：旧逻辑（兼容）
        print("[INFO] 使用V1系统（每任务所有人评）")
        
        all_tasks = []
        for j in judges:
            for p in prompts:
                vids = get_prompt_videos(conn, p)
                if not vids:
                    print(f"[WARN] Prompt {p} 没有视频，跳过")
                    continue
                for vid in vids:
                    all_tasks.append((j, p, vid))
        
        tasks_by_judge = {}
        for j, p, v in all_tasks:
            if j not in tasks_by_judge:
                tasks_by_judge[j] = []
            tasks_by_judge[j].append((p, v))
        
        total = 0
        for j in judges:
            tasks = tasks_by_judge.get(j, [])
            rnd = random.Random(f"{seed}-judge-{j}")
            rnd.shuffle(tasks)
            
            for p, v in tasks:
                cur.execute(
                    "INSERT INTO assignments(judge_id, prompt_id, order_json, finished) VALUES(?,?,?,0)",
                    (j, p, json.dumps([v]))
                )
                total += 1
        
        conn.commit()
        return len(judges), len(prompts), total

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--judges", type=int, default=10)
    ap.add_argument("--schema", default="db/schema.sql")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--keep", action="store_true", help="保留现有评审和数据，不清空数据库")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    conn = connect(args.db); ensure_schema(conn, args.schema)
    if not args.keep:
        reset_all(conn)
    rows = read_csv(args.csv); upsert_prompts_and_videos(conn, rows)
    toks = create_judges(conn, args.judges)
    nj, np, na = create_assignments(conn, seed=args.seed)

    # 检查系统版本
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
    is_v2 = cur.fetchone() is not None
    
    if is_v2:
        cur.execute("SELECT COUNT(*) FROM tasks")
        task_count = cur.fetchone()[0]
        print(f"[OK] 导入完成（V2系统）：")
        print(f"     - {np} 个prompts")
        print(f"     - {task_count} 个tasks（视频对）")
        print(f"     - {na} 个assignments（={task_count}×{nj}judges）")
        print(f"[INFO] 每个任务需3人评测，完成后自动从所有人列表中移除")
    else:
        print(f"[OK] 导入完成（V1系统）：prompts={np}, assignments={na}")
        print(f"     说明：每个评审员需要评测多个\"参考视频-生成视频对\"任务")
    print("\n=== 评审登录链接（请将 http 替换为 https 并去掉 :443，如 ngrok 隧道）===")
    for _, name, token in toks:
        print(f"{name}: http://{args.host}:{args.port}/?uid={token}")

if __name__ == "__main__":
    main()
