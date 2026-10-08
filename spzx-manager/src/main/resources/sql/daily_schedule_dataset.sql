-- 每日日程台账登记（scripts/daily_schedule.py）
-- 它是「这个作业几点跑」四份副本里的注册表那一份：机器上 crontab 有、卡片配置有、这里也得有。
-- measure=batch 而非 table：sys_user_schedule 也会被人工在页面上改，新鲜度只认台账的 finished_at
-- （见 IngestFreshnessService 注释：只有「每次成功运行都无条件写入」的表才能用 table）。
INSERT INTO ingest_dataset (code, name, measure, target_table, freshness_col, sla_hours,
                            monitor, writer, cron_expr, remark)
VALUES ('daily_schedule', '每日日程台账', 'batch', 'sys_user_schedule', NULL, 30,
        1, 'scripts/daily_schedule.py', '30 23 * * *',
        '每天 23:30 把当天跑批/告警/商品登记/质量分/两仓库提交汇总成后台「日程管理」的条目')
ON DUPLICATE KEY UPDATE name       = VALUES(name),
                        measure    = VALUES(measure),
                        target_table = VALUES(target_table),
                        sla_hours  = VALUES(sla_hours),
                        monitor    = VALUES(monitor),
                        writer     = VALUES(writer),
                        cron_expr  = VALUES(cron_expr),
                        remark     = VALUES(remark);
