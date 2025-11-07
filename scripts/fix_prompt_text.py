#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复prompts表中text字段的问题
- 有些记录的text字段等于id，需要从txt文件中读取真实的prompt文本
"""
import sqlite3
import sys
import io
from pathlib import Path

# Windows编码支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_prompt_category(sample_id: str) -> str:
    """从sample_id中提取category"""
    # 例如：animals_and_ecology_001_single -> animals_and_ecology
    parts = sample_id.split('_')
    
    # 处理不同的命名模式
    if len(parts) >= 3:
        # 找到第一个数字出现的位置
        for i, part in enumerate(parts):
            if part.isdigit():
                # 数字之前的部分是category
                return '_'.join(parts[:i])
    
    # 如果没有找到数字，使用前两个部分
    if len(parts) >= 2:
        return '_'.join(parts[:2])
    
    return parts[0] if parts else sample_id


def read_prompt_text(sample_id: str, prompt_root: Path) -> str | None:
    """从txt文件中读取prompt文本"""
    category = get_prompt_category(sample_id)
    txt_path = prompt_root / category / f"{sample_id}.txt"
    
    if txt_path.exists():
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"  ⚠️  读取文件失败 {txt_path}: {e}")
            return None
    else:
        print(f"  ⚠️  文件不存在: {txt_path}")
        return None


def fix_prompt_texts(db_path: str, prompt_root: Path):
    """修复所有text=id的记录"""
    print("=" * 80)
    print("  修复 prompts 表中的 text 字段")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 1. 找出所有text=id的记录
    cur.execute('SELECT id, sample_id FROM prompts WHERE text = id')
    problem_records = cur.fetchall()
    
    print(f"发现 {len(problem_records)} 条需要修复的记录")
    print()
    
    if not problem_records:
        print("✅ 没有需要修复的记录！")
        conn.close()
        return
    
    # 2. 逐个修复
    fixed_count = 0
    failed_count = 0
    
    for prompt_id, sample_id in problem_records:
        # 读取真实的prompt文本
        text = read_prompt_text(sample_id, prompt_root)
        
        if text:
            # 更新数据库
            cur.execute(
                'UPDATE prompts SET text = ? WHERE id = ?',
                (text, prompt_id)
            )
            fixed_count += 1
            
            if fixed_count <= 5:  # 只显示前5条
                print(f"✅ [{prompt_id}]")
                print(f"   {text[:100]}...")
                print()
        else:
            failed_count += 1
            print(f"❌ [{prompt_id}] - 无法读取文本")
    
    # 3. 提交更改
    conn.commit()
    
    print("=" * 80)
    print(f"修复完成！")
    print(f"  成功: {fixed_count}")
    print(f"  失败: {failed_count}")
    print("=" * 80)
    print()
    
    # 4. 验证
    cur.execute('SELECT COUNT(*) FROM prompts WHERE text = id')
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("✅ 所有记录已修复！")
    else:
        print(f"⚠️  仍有 {remaining} 条记录未修复")
    
    conn.close()


def main():
    db_path = 'aiv_eval_v4.db'
    prompt_root = Path('prompt')
    
    if not prompt_root.exists():
        print(f"❌ prompt目录不存在: {prompt_root}")
        return
    
    fix_prompt_texts(db_path, prompt_root)


if __name__ == '__main__':
    main()

