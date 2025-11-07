-- AIV Evaluation Database Schema
-- 3人评测制：每个任务只需3个评审员评测

-- 评审员表
CREATE TABLE IF NOT EXISTS judges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 提示词和参考视频表
CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,  -- sample_id
    text TEXT NOT NULL,
    ref_path TEXT,
    sample_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 生成视频表
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL,
    variant_index INTEGER NOT NULL,
    path TEXT NOT NULL,
    modelname TEXT,
    sample_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- 任务表 - 管理每个评测任务的生命周期
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL,              -- sample_id
    video_id INTEGER NOT NULL,            -- 关联videos表
    required_ratings INTEGER DEFAULT 3,   -- 需要的评测次数（默认3次）
    current_ratings INTEGER DEFAULT 0,    -- 当前已完成的评测次数
    completed INTEGER DEFAULT 0,          -- 是否完成（0=未完成，1=已完成）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,               -- 完成时间
    UNIQUE(prompt_id, video_id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
CREATE INDEX IF NOT EXISTS idx_tasks_prompt ON tasks(prompt_id);
CREATE INDEX IF NOT EXISTS idx_tasks_video ON tasks(video_id);

-- 任务分配表 - 关联task，所有judge看到所有未完成任务（顺序随机）
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judge_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,             -- 关联tasks表
    display_order INTEGER NOT NULL,       -- 该judge看到该任务的顺序（随机）
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished INTEGER DEFAULT 0,           -- 0=未完成，1=已完成
    finished_at TIMESTAMP,
    FOREIGN KEY (judge_id) REFERENCES judges(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    UNIQUE(judge_id, task_id)             -- 同一judge不会重复分配同一task
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_assignments_judge ON assignments(judge_id);
CREATE INDEX IF NOT EXISTS idx_assignments_task ON assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_assignments_finished ON assignments(finished);
CREATE INDEX IF NOT EXISTS idx_assignments_judge_order ON assignments(judge_id, display_order);

-- 评分记录表
CREATE TABLE IF NOT EXISTS ratings (
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
    UNIQUE(judge_id, video_id)  -- 同一评审员对同一视频只能有一个评分
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_ratings_judge ON ratings(judge_id);
CREATE INDEX IF NOT EXISTS idx_ratings_prompt ON ratings(prompt_id);
CREATE INDEX IF NOT EXISTS idx_ratings_video ON ratings(video_id);
CREATE INDEX IF NOT EXISTS idx_ratings_sample_model ON ratings(sample_id, modelname);

-- 触发器：当插入rating时自动更新task状态
CREATE TRIGGER IF NOT EXISTS update_task_on_rating_insert
AFTER INSERT ON ratings
FOR EACH ROW
BEGIN
    -- 更新task的current_ratings计数
    UPDATE tasks 
    SET current_ratings = (
        SELECT COUNT(DISTINCT judge_id) 
        FROM ratings 
        WHERE video_id = NEW.video_id
    )
    WHERE video_id = NEW.video_id;
    
    -- 如果达到required_ratings，标记为完成
    UPDATE tasks
    SET completed = 1,
        completed_at = CURRENT_TIMESTAMP
    WHERE video_id = NEW.video_id
      AND current_ratings >= required_ratings
      AND completed = 0;
END;

-- 触发器：当task完成时删除未完成的assignments
CREATE TRIGGER IF NOT EXISTS cleanup_assignments_on_task_complete
AFTER UPDATE OF completed ON tasks
FOR EACH ROW
WHEN NEW.completed = 1 AND OLD.completed = 0
BEGIN
    -- 删除该task所有未完成的assignments
    -- 但保留已有rating的assignments（用户可能在评测中，只是还没点提交）
    DELETE FROM assignments
    WHERE task_id = NEW.id
      AND finished = 0
      AND NOT EXISTS (
        SELECT 1 FROM ratings 
        WHERE ratings.judge_id = assignments.judge_id 
        AND ratings.video_id = NEW.video_id
      );
END;

-- 视图：任务完成度统计
CREATE VIEW IF NOT EXISTS task_completion_stats AS
SELECT 
    COUNT(*) as total_tasks,
    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_tasks,
    SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as pending_tasks,
    SUM(current_ratings) as total_ratings,
    SUM(required_ratings) as total_required_ratings,
    ROUND(100.0 * SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_rate
FROM tasks;

-- 视图：评审员工作统计
CREATE VIEW IF NOT EXISTS judge_workload_stats AS
SELECT 
    j.id as judge_id,
    j.name as judge_name,
    COUNT(DISTINCT a.id) as total_assigned,
    SUM(CASE WHEN a.finished = 1 THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN a.finished = 0 THEN 1 ELSE 0 END) as pending,
    COUNT(DISTINCT r.id) as total_ratings,
    ROUND(100.0 * SUM(CASE WHEN a.finished = 1 THEN 1 ELSE 0 END) / COUNT(DISTINCT a.id), 2) as completion_rate
FROM judges j
LEFT JOIN assignments a ON j.id = a.judge_id
LEFT JOIN ratings r ON j.id = r.judge_id
GROUP BY j.id, j.name;

-- 视图：任务详细信息
CREATE VIEW IF NOT EXISTS task_details AS
SELECT 
    t.id as task_id,
    t.prompt_id as sample_id,
    t.video_id,
    v.modelname,
    p.text as prompt_text,
    t.required_ratings,
    t.current_ratings,
    t.completed,
    t.created_at,
    t.completed_at,
    (t.required_ratings - t.current_ratings) as remaining_ratings
FROM tasks t
JOIN videos v ON t.video_id = v.id
JOIN prompts p ON t.prompt_id = p.id;

