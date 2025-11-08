-- AI视频生成比较评测系统 - 数据库结构
-- Version: Compare Mode v1.0
-- 说明：基于两两比较的评测系统，每个任务包含一个参考视频和两个生成视频

-- 1. 评审员表
CREATE TABLE IF NOT EXISTS judges (
    judge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,           -- 唯一访问token
    judge_name TEXT NOT NULL,           -- 评审员名称（如Judge-01）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 参考视频表（Prompt信息）
CREATE TABLE IF NOT EXISTS prompts (
    prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT UNIQUE NOT NULL,     -- 样本ID（如animals_001_single）
    category TEXT NOT NULL,             -- 类别（如animals_and_ecology）
    prompt_text TEXT NOT NULL,          -- Prompt文本描述
    ref_video_path TEXT NOT NULL,       -- 参考视频路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 生成视频表
CREATE TABLE IF NOT EXISTS videos (
    video_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT NOT NULL,            -- 对应的sample_id
    model_name TEXT NOT NULL,           -- 模型名称（如sora2, cogfun, kling）
    video_path TEXT NOT NULL,           -- 生成视频路径
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sample_id, model_name)
);

-- 4. 比较任务表（核心：两两配对）
CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id TEXT NOT NULL,            -- 参考视频的sample_id
    model_a TEXT NOT NULL,              -- 模型A名称
    model_b TEXT NOT NULL,              -- 模型B名称
    video_a_id INTEGER NOT NULL,        -- 模型A的video_id
    video_b_id INTEGER NOT NULL,        -- 模型B的video_id
    completed INTEGER DEFAULT 0,        -- 0=未完成，1=已完成（被评3次）
    current_ratings INTEGER DEFAULT 0,  -- 当前评分次数（0-3）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (video_a_id) REFERENCES videos(video_id),
    FOREIGN KEY (video_b_id) REFERENCES videos(video_id),
    UNIQUE(sample_id, model_a, model_b),  -- 防止重复配对
    CHECK(model_a < model_b)              -- 确保字母序，避免(A,B)和(B,A)重复
);

-- 5. 任务分配表（每个评审员看到的任务列表）
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    position INTEGER NOT NULL,          -- 任务在该评审员列表中的位置（随机顺序）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (judge_id) REFERENCES judges(judge_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    UNIQUE(judge_id, task_id)
);

-- 6. 比较结果表（评审员的选择）
CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    judge_id INTEGER NOT NULL,
    chosen_model TEXT NOT NULL,         -- 选择的模型名称（model_a或model_b）
    comment TEXT,                       -- 可选的评论
    rating_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (judge_id) REFERENCES judges(judge_id),
    UNIQUE(task_id, judge_id)           -- 每个评审员对每个任务只能评一次
);

-- 创建索引（提升查询性能）
CREATE INDEX IF NOT EXISTS idx_tasks_sample_id ON tasks(sample_id);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
CREATE INDEX IF NOT EXISTS idx_videos_sample_id ON videos(sample_id);
CREATE INDEX IF NOT EXISTS idx_videos_model ON videos(model_name);
CREATE INDEX IF NOT EXISTS idx_assignments_judge ON assignments(judge_id);
CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_task ON comparisons(task_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_judge ON comparisons(judge_id);

-- 触发器1：评分插入时更新任务状态
CREATE TRIGGER IF NOT EXISTS update_task_on_comparison_insert
AFTER INSERT ON comparisons
BEGIN
    -- 更新当前评分次数
    UPDATE tasks 
    SET current_ratings = (
        SELECT COUNT(*) FROM comparisons WHERE task_id = NEW.task_id
    )
    WHERE task_id = NEW.task_id;
    
    -- 如果达到3次评分，标记为完成
    UPDATE tasks 
    SET completed = 1
    WHERE task_id = NEW.task_id 
    AND current_ratings >= 3;
END;

-- 触发器2：任务完成时清理未评分的分配记录
CREATE TRIGGER IF NOT EXISTS cleanup_assignments_on_task_complete
AFTER UPDATE OF completed ON tasks
WHEN NEW.completed = 1
BEGIN
    -- 删除未评分的分配（保留已评分的）
    DELETE FROM assignments
    WHERE task_id = NEW.task_id
    AND judge_id NOT IN (
        SELECT judge_id FROM comparisons WHERE task_id = NEW.task_id
    );
END;

