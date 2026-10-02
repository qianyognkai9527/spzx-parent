-- videogen_cost_guard.sql : 成本护栏（单价列 + 预计扣费列 + 日预算配置）
-- 幂等写法：列/行已存在时报 Duplicate/键冲突可安全忽略后续语句

-- 1) kw_provider 增加视频 5 秒档单价（元）。2) video_gen_task 增加本单预计扣费快照
ALTER TABLE kw_provider ADD COLUMN video_price DECIMAL(8,2) DEFAULT NULL COMMENT '视频生成5秒档单价(元)，NULL=未配置不计费';
ALTER TABLE video_gen_task ADD COLUMN est_cost DECIMAL(8,2) DEFAULT NULL COMMENT '创建时预计扣费(元)=单价×时长/5';

-- 3) 方舟 provider 播种实测单价（Seedance 2.5 账单实证 ¥7.67/5s；当前模型 1-0-pro 单价待出账后按账单修正）
UPDATE kw_provider SET video_price = 7.67 WHERE name = 'volcengine-ark' AND video_price IS NULL;

-- 4) 视频日预算（元）：当日创建任务 est_cost 合计 + 本单 > 预算 → 拒绝创建。INSERT IGNORE 幂等，留空=不限制
INSERT IGNORE INTO kw_config (config_key, config_value) VALUES ('video_daily_budget', '');
