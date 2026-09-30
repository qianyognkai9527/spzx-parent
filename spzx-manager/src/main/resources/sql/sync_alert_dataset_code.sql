-- SyncAlert 数据集归属列：让「恢复新鲜」能自动关闭对应的过期告警
-- 对应 IngestFreshnessService.closeOpenAlerts：数据集追平后把该数据集仍未读的 ingest_stale
-- 置为 status=2（已恢复），不再靠人肉点「已读」。
-- 此前告警只写了 alert_type/old_value(最后写入时刻)/new_value(SLA)，Java 侧认不出哪条属于哪个数据集，
-- 于是「已 59 小时没有成功采集」会在数据早已追平的情况下永久挂在看板上。
--
-- 执行：mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < sync_alert_dataset_code.sql
-- 重复执行前先用 SHOW COLUMNS FROM sync_alert LIKE 'dataset_code' 确认（ALTER 不可重复）。

ALTER TABLE sync_alert
  ADD COLUMN dataset_code VARCHAR(32) NULL COMMENT '采集契约类告警所属 ingest_dataset.code，其他类型为 NULL' AFTER alert_type;

-- 历史 ingest_stale 行回填：这类告警的 message 由 insertAlert 固定生成，开头是「<数据集名>」，
-- 名称到 code 的映射只能从 ingest_dataset 取，写死中文名的话下次改名就回填不上。
UPDATE sync_alert sa
  JOIN ingest_dataset d
    ON sa.alert_type = 'ingest_stale'
   AND sa.dataset_code IS NULL
   AND sa.message LIKE CONCAT('「', d.name, '」%')
   SET sa.dataset_code = d.code;

-- 不加索引：sync_alert 是几百行量级的小表，扫描任务每小时一次按 (alert_type, dataset_code, status)
-- 更新个位数行，建索引只是多一处要维护的东西。表若长到万行再回来加。

-- 自检：回填后仍为 NULL 的 ingest_stale 行数应为 0
SELECT COUNT(*) AS unresolved_ingest_stale
FROM sync_alert WHERE alert_type = 'ingest_stale' AND dataset_code IS NULL;
