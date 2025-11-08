#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较评测模式 - 数据准备脚本
扫描video2目录，找到每个参考视频对应的所有生成视频，生成两两配对的任务清单
"""

import os
import csv
from pathlib import Path
from collections import defaultdict
import itertools

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 目录配置
REF_VIDEO_DIR = PROJECT_ROOT / "video" / "refvideo"
GEN_VIDEO_DIR = PROJECT_ROOT / "video2"
PROMPT_DIR = PROJECT_ROOT / "prompt"
OUTPUT_CSV = PROJECT_ROOT / "data" / "comparison_tasks.csv"


def scan_ref_videos():
    """扫描参考视频目录"""
    ref_videos = {}
    print("📹 扫描参考视频...")
    
    if not REF_VIDEO_DIR.exists():
        print(f"❌ 参考视频目录不存在: {REF_VIDEO_DIR}")
        return ref_videos
    
    for category_dir in REF_VIDEO_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        
        category_name = category_dir.name
        sub_dir = category_dir / category_name
        
        if not sub_dir.exists():
            continue
        
        for video_file in sub_dir.glob("*.mp4"):
            sample_id = video_file.stem  # 如 animals_001_single
            ref_videos[sample_id] = {
                'category': category_name,
                'path': str(video_file.relative_to(PROJECT_ROOT))
            }
    
    print(f"   找到 {len(ref_videos)} 个参考视频")
    return ref_videos


def scan_gen_videos():
    """扫描生成视频目录（video2）"""
    gen_videos = defaultdict(list)  # {sample_id: [(model_name, video_path), ...]}
    print("\n🤖 扫描生成视频（video2）...")
    
    if not GEN_VIDEO_DIR.exists():
        print(f"❌ 生成视频目录不存在: {GEN_VIDEO_DIR}")
        return gen_videos
    
    for model_dir in GEN_VIDEO_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_name = model_dir.name
        sub_dir = model_dir / model_name
        
        if not sub_dir.exists():
            # 尝试直接在model_dir下查找视频
            sub_dir = model_dir
        
        for video_file in sub_dir.glob("*.mp4"):
            sample_id = video_file.stem
            video_path = str(video_file.relative_to(PROJECT_ROOT))
            gen_videos[sample_id].append((model_name, video_path))
    
    # 统计
    total_videos = sum(len(videos) for videos in gen_videos.values())
    print(f"   找到 {total_videos} 个生成视频")
    print(f"   覆盖 {len(gen_videos)} 个样本")
    
    # 显示每个样本的模型数量
    model_counts = defaultdict(int)
    for sample_id, videos in gen_videos.items():
        model_counts[len(videos)] += 1
    
    print("\n   模型数量分布:")
    for count in sorted(model_counts.keys()):
        print(f"     {count}个模型: {model_counts[count]}个样本")
    
    return gen_videos


def load_prompt_text(sample_id, category):
    """加载Prompt文本"""
    prompt_file = PROMPT_DIR / category / f"{sample_id}.txt"
    
    if prompt_file.exists():
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        return f"[Prompt文件缺失: {sample_id}]"


def generate_comparison_tasks(ref_videos, gen_videos):
    """生成两两配对的比较任务"""
    print("\n⚙️  生成比较任务...")
    
    tasks = []
    skipped_samples = []
    
    for sample_id, ref_info in ref_videos.items():
        # 检查是否有对应的生成视频
        if sample_id not in gen_videos:
            skipped_samples.append(sample_id)
            continue
        
        models = gen_videos[sample_id]
        
        # 只有2个或更多生成视频才能配对
        if len(models) < 2:
            continue
        
        # 加载Prompt文本
        prompt_text = load_prompt_text(sample_id, ref_info['category'])
        
        # 生成所有可能的配对（排列组合）
        for (model_a, video_a_path), (model_b, video_b_path) in itertools.combinations(models, 2):
            # 确保字母序（model_a < model_b）
            if model_a > model_b:
                model_a, model_b = model_b, model_a
                video_a_path, video_b_path = video_b_path, video_a_path
            
            tasks.append({
                'sample_id': sample_id,
                'category': ref_info['category'],
                'prompt_text': prompt_text,
                'ref_video_path': ref_info['path'],
                'model_a': model_a,
                'model_b': model_b,
                'video_a_path': video_a_path,
                'video_b_path': video_b_path
            })
    
    print(f"   ✅ 生成 {len(tasks)} 个比较任务")
    print(f"   ⚠️  跳过 {len(skipped_samples)} 个样本（无生成视频或只有1个）")
    
    return tasks


def save_tasks_to_csv(tasks):
    """保存任务清单到CSV"""
    print(f"\n💾 保存任务清单到: {OUTPUT_CSV}")
    
    # 确保data目录存在
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sample_id', 'category', 'prompt_text', 'ref_video_path',
            'model_a', 'model_b', 'video_a_path', 'video_b_path'
        ])
        writer.writeheader()
        writer.writerows(tasks)
    
    print(f"   ✅ 保存成功！")


def main():
    print("="*80)
    print("比较评测模式 - 数据准备")
    print("="*80)
    
    # 1. 扫描参考视频
    ref_videos = scan_ref_videos()
    if not ref_videos:
        print("\n❌ 没有找到参考视频，退出")
        return
    
    # 2. 扫描生成视频
    gen_videos = scan_gen_videos()
    if not gen_videos:
        print("\n❌ 没有找到生成视频，退出")
        return
    
    # 3. 生成比较任务
    tasks = generate_comparison_tasks(ref_videos, gen_videos)
    if not tasks:
        print("\n❌ 没有生成任何任务（需要每个样本至少2个生成视频）")
        return
    
    # 4. 保存到CSV
    save_tasks_to_csv(tasks)
    
    print("\n" + "="*80)
    print("✅ 数据准备完成！")
    print("="*80)
    print(f"\n下一步：运行 python scripts\\setup_project_compare.py --judges 10")


if __name__ == "__main__":
    main()

