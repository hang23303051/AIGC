#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 获取评审员访问链接
显示所有评审员的带UID的访问链接
"""

import sqlite3
import socket
from pathlib import Path

# 配置
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "aiv_compare_v1.db"
UI_PORT = 8503


def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"


def get_judge_links():
    """获取所有评审员链接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT judge_id, judge_name, uid
        FROM judges
        ORDER BY judge_name
    """)
    
    judges = cursor.fetchall()
    conn.close()
    
    return judges


def main():
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        print("   请先运行: python scripts\\setup_project_compare.py")
        return
    
    local_ip = get_local_ip()
    
    print("="*80)
    print("比较评测模式 - 评审员访问链接")
    print("="*80)
    print()
    
    judges = get_judge_links()
    
    if not judges:
        print("⚠️  没有找到评审员")
        return
    
    print(f"本机IP: {local_ip}")
    print(f"UI端口: {UI_PORT}")
    print()
    print("="*80)
    print()
    
    for judge in judges:
        judge_name = judge['judge_name']
        uid = judge['uid']
        
        print(f"【{judge_name}】")
        print(f"  http://{local_ip}:{UI_PORT}/?uid={uid}")
        print()
    
    print("="*80)
    print()
    print("💡 提示:")
    print("  1. 将对应链接发送给评审员")
    print("  2. 评审员在浏览器中打开链接即可开始评测")
    print("  3. 确保服务已启动: .\\lan_start_compare.ps1")
    print()


if __name__ == "__main__":
    main()

