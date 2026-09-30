-- SyncAlert 外部告警通道（钉钉 webhook）所需列
-- 对应 SyncAlertNotifyTask：每分钟扫 notified=0 的行推送，成功后置 1。
--
-- [现状] 本地 db_spzx 已核实该列存在且定义与下方一致（tinyint NOT NULL DEFAULT 0 + idx_notified），
--         只是当初手工执行没落成脚本 —— 换库/重建时若漏执行，MyBatis-Plus 的显式列查询会直接
--         报 Unknown column 'notified'，告警列表与推送任务一起挂。
-- 执行：mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < sync_alert_notify_channel.sql
-- 重复执行前先用 SHOW COLUMNS FROM sync_alert LIKE 'notified' 确认。

ALTER TABLE sync_alert
  ADD COLUMN notified TINYINT NOT NULL DEFAULT 0 COMMENT '是否已推送外部告警 0否1是' AFTER status;

CREATE INDEX idx_notified ON sync_alert (notified, status);

-- 说明：automation/sourcing/detect_alerts.py 的 INSERT 不写这一列，靠 DEFAULT 0 兜底。
-- 因此这里必须是 NOT NULL DEFAULT 0 —— 若允许 NULL，SyncAlertNotifyTask 的 eq(notified,0)
-- 永远匹配不上，告警会静默不推送。
