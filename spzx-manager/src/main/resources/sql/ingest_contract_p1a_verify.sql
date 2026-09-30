-- P1a 采集契约 建表后对账 / 自检
--   mysql --defaults-extra-file=/tmp/spzx_my.cnf --default-character-set=utf8mb4 -D db_spzx < ingest_contract_p1a_verify.sql
-- 期望：V1=3 张表且注释无乱码；V2 monitor=1 的行数=6（2026-09-29 实况，加数据集时同步这行）；
--       V3 违例=0（种子的 target_table/freshness_col 必须真实存在）；
--       V4 业务表行数与建表前一致（本脚本只做加法，不该动任何业务数据）；F* 是当前新鲜度实况。

-- V1 表与注释（双重编码会在这里显形）
SELECT TABLE_NAME, TABLE_COMMENT,
       IF(TABLE_COMMENT REGEXP '[^一-龥a-zA-Z0-9_ ]', 'CHECK', 'ok') comment_scan
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE 'ingest%'
ORDER BY TABLE_NAME;

-- V2 种子
SELECT COUNT(*) AS datasets_total,
       SUM(monitor = 1) AS monitored,
       SUM(measure = 'table') AS measure_table,
       SUM(measure = 'batch') AS measure_batch
FROM ingest_dataset;

-- V3 种子自洽性违例（只判 monitor=1 的行：它们会真的产生告警）
--   batch 量法此前不校验，target_table 写错只是注释骗人；现在它也在骗看板，故一起查
SELECT d.code, d.measure, d.target_table, d.freshness_col,
       CASE WHEN t.TABLE_NAME IS NULL THEN '表不存在'
            WHEN d.measure = 'table' AND d.freshness_col IS NULL THEN 'table 量法缺心跳列'
            WHEN d.measure = 'table' AND c.COLUMN_NAME IS NULL THEN '心跳列不存在'
            WHEN d.measure = 'batch' AND d.freshness_col IS NOT NULL THEN 'batch 量法不该有心跳列'
            WHEN d.sla_hours <= 0 THEN 'SLA 非正' END AS problem
FROM ingest_dataset d
LEFT JOIN information_schema.TABLES t
       ON t.TABLE_SCHEMA = DATABASE() AND t.TABLE_NAME = d.target_table
LEFT JOIN information_schema.COLUMNS c
       ON c.TABLE_SCHEMA = DATABASE() AND c.TABLE_NAME = d.target_table AND c.COLUMN_NAME = d.freshness_col
WHERE d.monitor = 1
HAVING problem IS NOT NULL;

-- V4 业务表未被触碰（与建表前记下的行数比对）
SELECT 'order_info' AS t, COUNT(*) AS n FROM order_info
UNION ALL SELECT 'platform_product', COUNT(*) FROM platform_product
UNION ALL SELECT 'source_sku', COUNT(*) FROM source_sku
UNION ALL SELECT 'sycm_item_effect_history', COUNT(*) FROM sycm_item_effect_history
UNION ALL SELECT 'sync_alert', COUNT(*) FROM sync_alert;

-- F1 纳入告警数据集的当前心跳（table 量法）
SELECT d.code, d.name, d.sla_hours,
       MAX(CASE WHEN d.target_table = 'sycm_item_effect_history' THEN s.snapshot_time
                WHEN d.target_table = 'source_sku' THEN k.update_time END) AS last_write,
       TIMESTAMPDIFF(HOUR,
         MAX(CASE WHEN d.target_table = 'sycm_item_effect_history' THEN s.snapshot_time
                  WHEN d.target_table = 'source_sku' THEN k.update_time END), NOW()) AS age_hours,
       IF(TIMESTAMPDIFF(HOUR,
         MAX(CASE WHEN d.target_table = 'sycm_item_effect_history' THEN s.snapshot_time
                  WHEN d.target_table = 'source_sku' THEN k.update_time END), NOW()) > d.sla_hours,
         'STALE', 'fresh') AS health
FROM ingest_dataset d
LEFT JOIN sycm_item_effect_history s ON d.target_table = 'sycm_item_effect_history'
LEFT JOIN source_sku k ON d.target_table = 'source_sku'
WHERE d.monitor = 1 AND d.measure = 'table'
GROUP BY d.code, d.name, d.sla_hours;

-- F2 batch 量法实况：P1b 起 4 个货源侧数据集有真实写入方（cron_batch.py / grade_quality.py），
--    monitor=1 且 landed_batches=0 只允许出现在"台账刚建立"的那一轮；pdd 契约预留行本来就应为空。
--    measure=table 的两个数据集走心跳列判新鲜，本表恒为 0，不是故障。
SELECT d.code, d.name, d.monitor,
       IFNULL(SUM(b.status IN ('success', 'partial')), 0) AS landed_batches,
       IFNULL(SUM(b.status = 'failed'), 0) AS failed_batches,
       MAX(CASE WHEN b.status IN ('success', 'partial') THEN b.finished_at END) AS last_success
FROM ingest_dataset d
LEFT JOIN ingest_batch b ON b.dataset = d.code
GROUP BY d.code, d.name, d.monitor
ORDER BY d.monitor DESC, d.code;
