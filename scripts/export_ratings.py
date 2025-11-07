import argparse, sqlite3, csv
from collections import defaultdict
import os

# 根据数据规模定义模型列表
# 可以通过环境变量 AIV_DATA_SCALE 控制
_use_large_scale = os.getenv('AIV_DATA_SCALE', 'large') == 'large'

if _use_large_scale:
    # 大规模数据：5个模型
    MODELS = ['wan21', 'vidu', 'cogfun', 'cogvideo5b', 'videocrafter']
else:
    # 小规模数据：7个模型
    MODELS = ['wan21', 'kling', 'jimeng', 'opensora', 'cogfun', 'cogvideo_5b', 'videocrafter']

def main():
    ap = argparse.ArgumentParser(description='导出评分数据（支持7个模型，未评测的模型留空）')
    ap.add_argument("--db", required=True, help='数据库路径')
    ap.add_argument("--out", required=True, help='输出CSV路径')
    ap.add_argument("--format", choices=['wide', 'long'], default='wide', 
                   help='导出格式：wide=宽表（每个模型一列），long=长表（原始格式）')
    args = ap.parse_args()
    
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
    
    if args.format == 'long':
        # 原始长表格式：每个评分一行
        cur.execute(
            """
            SELECT r.id, r.created_at,
                   j.id as judge_id, j.name as judge_name,
                   p.id as prompt_id, p.text as prompt_text,
                   v.id as video_id, v.variant_index, v.modelname, v.path as video_path,
                   r.score_semantic, r.score_motion, r.score_temporal, r.score_realism
            FROM ratings r
            JOIN judges j ON j.id = r.judge_id
            JOIN videos v ON v.id = r.video_id
            JOIN prompts p ON p.id = v.prompt_id
            ORDER BY j.id, p.id, v.modelname
            """
        )
        rows = cur.fetchall()
        header = ["rating_id","created_at","judge_id","judge_name","sample_id","prompt_text",
                 "video_id","variant","modelname","video_path","score_semantic","score_motion","score_temporal","score_realism"]
        with open(args.out,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(header); w.writerows(rows)
        print(f"[OK] 导出 {len(rows)} 条评分（长表格式） -> {args.out}")
    
    else:
        # 宽表格式：每个prompt+judge一行，每个模型的4个维度各占一列
        # 结构：judge_id, judge_name, sample_id, prompt_text, 
        #       [modelname]_semantic, [modelname]_motion, [modelname]_temporal, [modelname]_realism (x7个模型)
        
        # 收集数据：(judge_id, prompt_id) -> {model: {scores}}
        data = defaultdict(lambda: {
            'judge_name': None,
            'prompt_text': None,
            'models': {model: {'semantic': '', 'motion': '', 'temporal': '', 'realism': ''} for model in MODELS}
        })
        
        cur.execute(
            """
            SELECT j.id as judge_id, j.name as judge_name,
                   p.id as prompt_id, p.text as prompt_text,
                   v.modelname,
                   r.score_semantic, r.score_motion, r.score_temporal, r.score_realism
            FROM ratings r
            JOIN judges j ON j.id = r.judge_id
            JOIN videos v ON v.id = r.video_id
            JOIN prompts p ON p.id = v.prompt_id
            ORDER BY j.id, p.id
            """
        )
        
        for row in cur.fetchall():
            judge_id, judge_name, prompt_id, prompt_text, model, sem, mot, tem, rea = row
            key = (judge_id, prompt_id)
            data[key]['judge_name'] = judge_name
            data[key]['prompt_text'] = prompt_text
            if model in data[key]['models']:
                data[key]['models'][model] = {
                    'semantic': sem,
                    'motion': mot,
                    'temporal': tem,
                    'realism': rea
                }
        
        # 构建宽表
        header = ['judge_id', 'judge_name', 'sample_id', 'prompt_text']
        for model in MODELS:
            header.extend([
                f'{model}_semantic',
                f'{model}_motion',
                f'{model}_temporal',
                f'{model}_realism'
            ])
        
        rows = []
        for (judge_id, prompt_id), entry in sorted(data.items()):
            row = [judge_id, entry['judge_name'], prompt_id, entry['prompt_text']]
            for model in MODELS:
                scores = entry['models'][model]
                row.extend([
                    scores['semantic'],
                    scores['motion'],
                    scores['temporal'],
                    scores['realism']
                ])
            rows.append(row)
        
        with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        
        print(f"[OK] 导出 {len(rows)} 个评测任务（宽表格式，{len(MODELS)}个模型） -> {args.out}")
        print(f"     每个模型4个维度，未评测的模型留空")

if __name__ == "__main__":
    main()
