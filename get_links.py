import sqlite3
import socket
import os

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(project_root, 'aiv_eval_v4.db')
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        print("Please run prepare_data.py and setup_project.py first.")
        return

    local_ip = get_local_ip()
    ui_port = 8502

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name, token FROM judges ORDER BY id")
    judges = cur.fetchall()
    conn.close()

    print("============================================================")
    print("  Reviewer Access Links")
    print("============================================================")
    print(f"\nLocal IP: {local_ip}")
    print(f"Database: {os.path.basename(db_path)}")
    print(f"Models: 5 (wan21, vidu, cogfun, cogvideo5b, videocrafter)\n")

    if not judges:
        print("[INFO] No reviewers found in the database.")
        print("Please run scripts/setup_project.py to create reviewers.")
        return

    for name, token in judges:
        print(f"{name}: http://{local_ip}:{ui_port}/?uid={token}")

    print("\n============================================================")
    print(f"Total: {len(judges)} reviewers")
    print("============================================================")

if __name__ == '__main__':
    main()

