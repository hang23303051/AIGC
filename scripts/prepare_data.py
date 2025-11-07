import os
import re
import csv
import shutil
import argparse
import socket
from pathlib import Path


# 大规模数据的5个模型
MODELS = ['wan21', 'vidu', 'cogfun', 'cogvideo5b', 'videocrafter']


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def sample_category(sample_id: str) -> str | None:
    """从sample_id提取类别，支持新的命名格式：category_number_type"""
    # 匹配格式：{category}_{number}_{type} (如 food_001_multi)
    m = re.match(r'^(.+)_(\d{3})_(multi|single)$', sample_id)
    return m.group(1) if m else None


def read_prompt_text(sample_id: str, prompt_root: Path) -> str:
    """读取sample_id对应的prompt文本文件"""
    cat = sample_category(sample_id)
    if not cat:
        return sample_id
    
    prompt_file = prompt_root / cat / f'{sample_id}.txt'
    if prompt_file.exists():
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[WARN] 无法读取prompt文件 {prompt_file}: {e}")
    return sample_id


def find_all_reference_videos(ref_root: Path) -> dict[str, Path]:
    """
    扫描参考视频目录，返回所有参考视频的映射: sample_id -> ref_video_path
    处理两层嵌套目录结构：refvideo/category/category/*.mp4
    """
    ref_mapping: dict[str, Path] = {}
    
    # 遍历所有类别目录
    for cat_dir in ref_root.iterdir():
        if not cat_dir.is_dir():
            continue
        
        # 处理两层嵌套：refvideo/category/category/
        inner_dir = cat_dir / cat_dir.name
        if not inner_dir.exists():
            # 尝试单层目录
            inner_dir = cat_dir
        
        # 扫描所有mp4文件
        for p in inner_dir.glob('*.mp4'):
            sid = p.stem  # 文件名不带扩展名即为sample_id
            ref_mapping[sid] = p
    
    return ref_mapping


def find_generated_videos(gen_root: Path, ref_samples: set[str]) -> dict[str, dict[str, Path]]:
    """
    为参考视频列表查找对应的生成视频
    返回映射: sample_id -> { model: path }
    处理两层嵌套目录结构：genvideo/model/model/*.mp4
    """
    mapping: dict[str, dict[str, Path]] = {}
    
    for model in MODELS:
        # 处理两层嵌套：genvideo/model/model/
        model_base = gen_root / model / model
        if not model_base.exists():
            # 尝试单层目录
            model_base = gen_root / model
        
        if not model_base.exists():
            print(f"[WARN] 模型目录不存在: {model_base}")
            continue
        
        # 扫描所有mp4文件
        for p in model_base.glob('*.mp4'):
            sid = p.stem  # 文件名不带扩展名即为sample_id
            # 只记录那些有对应参考视频的生成视频
            if sid in ref_samples:
                mapping.setdefault(sid, {})[model] = p
    
    return mapping


def ensure_static_layout(static_root: Path, samples: list[str], 
                         sources: dict[str, dict[str, Path]], 
                         ref_root: Path) -> None:
    """
    创建静态服务目录结构：
    - human_eval_v4/ref/<sample_id>/ref.mp4
    - human_eval_v4/gen/<sample_id>/<model>.mp4
    """
    for sid in samples:
        # 复制生成视频
        gdir = static_root / 'gen' / sid
        gdir.mkdir(parents=True, exist_ok=True)
        for model, src in sources[sid].items():
            dst = gdir / f'{model}.mp4'
            if not dst.exists() or os.path.getsize(dst) == 0:
                shutil.copy2(src, dst)
        
        # 复制参考视频
        rdir = static_root / 'ref' / sid
        rdir.mkdir(parents=True, exist_ok=True)
        cat = sample_category(sid)
        if cat:
            # 处理两层嵌套：refvideo/category/category/*.mp4
            ref_src = ref_root / cat / cat / f'{sid}.mp4'
            if not ref_src.exists():
                # 尝试单层目录
                ref_src = ref_root / cat / f'{sid}.mp4'
            
            if ref_src.exists():
                dst = rdir / 'ref.mp4'
                if not dst.exists() or os.path.getsize(dst) == 0:
                    shutil.copy2(ref_src, dst)
            else:
                print(f"[WARN] 参考视频不存在: {ref_src}")


def write_csv(csv_path: Path, video_base: str, samples: list[str], 
              sources: dict[str, dict[str, Path]], prompt_root: Path) -> None:
    """
    写入CSV文件，格式：
    sample_id, prompt_text, ref_path, variant, gen_path
    """
    rows = []
    for sid in samples:
        ref = f"{video_base}/ref/{sid}/ref.mp4"
        prompt_text = read_prompt_text(sid, prompt_root)
        present = [m for m in MODELS if m in sources.get(sid, {})]
        
        for i, model in enumerate(present, start=1):
            gen = f"{video_base}/gen/{sid}/{model}.mp4"
            rows.append({
                'prompt_id': sid,
                'prompt_text': prompt_text,
                'ref_path': ref,
                'variant': i,
                'gen_path': gen,
            })
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['prompt_id', 'prompt_text', 'ref_path', 'variant', 'gen_path'])
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description='准备评测数据（5个模型：wan21, vidu, cogfun, cogvideo5b, videocrafter）')
    
    project_root = Path(__file__).parent.parent
    
    # 自动获取本机局域网IP
    local_ip = get_local_ip()
    default_video_base = f'http://{local_ip}:8010'
    
    # 数据目录配置
    ap.add_argument('--gen-root', default=str(project_root / 'video' / 'genvideo'), 
                   help='生成视频根目录')
    ap.add_argument('--ref-root', default=str(project_root / 'video' / 'refvideo'), 
                   help='参考视频根目录')
    ap.add_argument('--prompt-root', default=str(project_root / 'prompt'), 
                   help='prompt文本根目录')
    ap.add_argument('--static-root', default=str(project_root / 'video' / 'human_eval_v4'), 
                   help='静态服务根目录')
    ap.add_argument('--csv-out', default='data/prompts.csv', 
                   help='输出CSV路径')
    ap.add_argument('--video-base', default=default_video_base, 
                   help='视频base URL (局域网IP:8010)')
    ap.add_argument('--local-ip', default=local_ip, 
                   help='本机局域网IP地址（自动检测）')
    
    args = ap.parse_args()
    
    print(f"[INFO] 检测到本机局域网IP: {args.local_ip}")
    print(f"[INFO] 视频URL将使用: {args.video_base}")
    print(f"[INFO] 模型列表: {', '.join(MODELS)}")
    
    gen_root = Path(args.gen_root)
    ref_root = Path(args.ref_root)
    prompt_root = Path(args.prompt_root)
    static_root = Path(args.static_root)
    
    # 1. 扫描参考视频（这是基准）
    print(f"\n[1/5] 扫描参考视频目录: {ref_root}")
    ref_mapping = find_all_reference_videos(ref_root)
    all_samples = sorted(ref_mapping.keys())
    print(f"      发现 {len(all_samples)} 个参考视频")
    
    # 2. 扫描生成视频
    print(f"\n[2/5] 扫描生成视频目录: {gen_root}")
    gen_mapping = find_generated_videos(gen_root, set(all_samples))
    
    # 统计每个模型的视频数量
    model_counts = {}
    total_gen_videos = 0
    for sid, models in gen_mapping.items():
        for model in models.keys():
            model_counts[model] = model_counts.get(model, 0) + 1
            total_gen_videos += 1
    
    print(f"      找到 {total_gen_videos} 个生成视频")
    print(f"\n      各模型视频数量:")
    for model in MODELS:
        count = model_counts.get(model, 0)
        print(f"        {model:<15} {count:>4} 个视频")
    
    # 统计有多少参考视频找到了至少一个生成视频
    samples_with_gen = len(gen_mapping)
    samples_without_gen = len(all_samples) - samples_with_gen
    print(f"\n      {samples_with_gen} 个参考视频有生成视频")
    if samples_without_gen > 0:
        print(f"      {samples_without_gen} 个参考视频没有找到生成视频（将跳过）")
    
    # 只处理有生成视频的样本
    samples_to_process = sorted(gen_mapping.keys())
    
    # 3. 创建静态服务目录
    print(f"\n[3/5] 创建静态服务目录: {static_root}")
    ensure_static_layout(static_root, samples_to_process, gen_mapping, ref_root)
    print(f"      完成")
    
    # 4. 写入CSV
    print(f"\n[4/5] 生成CSV文件: {args.csv_out}")
    csv_out = Path(args.csv_out)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(csv_out, args.video_base, samples_to_process, gen_mapping, prompt_root)
    
    # 统计CSV行数
    with open(csv_out, 'r', encoding='utf-8-sig') as f:
        csv_rows = sum(1 for _ in f) - 1  # 减去header
    
    print(f"      CSV包含 {csv_rows} 行数据")
    
    # 5. 总结
    print(f"\n[5/5] 完成！")
    print(f"\n" + "=" * 70)
    print(f"  数据准备完成")
    print(f"=" * 70)
    print(f"  参考视频总数: {len(all_samples)}")
    print(f"  有生成视频的参考视频: {samples_with_gen}")
    print(f"  生成视频总数: {total_gen_videos}")
    print(f"  模型数: {len(MODELS)}")
    print(f"  CSV行数: {csv_rows} (每行一个参考视频-生成视频对)")
    print(f"  静态目录: {static_root}")
    print(f"  CSV文件: {csv_out}")
    print(f"=" * 70)
    print(f"\n下一步:")
    print(f"  D:\\miniconda3\\envs\\learn\\python.exe scripts\\setup_project.py \\")
    print(f"    --db aiv_eval_v4.db \\")
    print(f"    --csv {csv_out} \\")
    print(f"    --judges 10")
    print()


if __name__ == '__main__':
    main()

