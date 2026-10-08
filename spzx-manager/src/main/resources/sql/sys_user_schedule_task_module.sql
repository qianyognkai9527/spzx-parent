-- ============================================
-- 工作留痕：日程任务表增加 module（模块）列
-- 用途：scripts/log_work.py 把 AI/手工代记的活按模块归类写入当天日程；
--       自动台账（daily_schedule.py，create_by=0）写入的行 module 保持 NULL。
-- 可重复执行：先查 information_schema，列已存在则跳过 ALTER。
-- ============================================

SET @ddl := (
    SELECT IF(
        EXISTS(SELECT 1 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'sys_user_schedule_task'
                 AND COLUMN_NAME = 'module'),
        'DO 0',  -- 列已存在：空操作，保持重跑静默
        'ALTER TABLE sys_user_schedule_task '
        'ADD COLUMN module VARCHAR(30) NULL COMMENT ''任务模块（自由文本，AI 留痕用）'' AFTER task_title'
    )
);

PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
