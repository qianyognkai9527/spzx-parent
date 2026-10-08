-- 一次性回填：给历史 cron_skipped / cron_failed 提醒补上销案依据 dataset_code
--
-- 背景：cron_alert.py 以前不写 dataset_code，后端因此没有任何依据判断"这个作业后来跑成了"，
-- 那批提醒只能人工清（2026-10-07 顶栏挂着 7 条未读，其中 5 条的作业早已恢复）。
-- 现在写入方补了 --dataset，这条只管修历史行；映射与 automation/*/cron_*.sh 里的 --dataset 一致。
-- 幂等：只动 dataset_code 仍为空的行，重跑无副作用。

UPDATE sync_alert
SET dataset_code = CASE old_value
        WHEN 'alimama_promo'     THEN 'promo_cost'
        WHEN 'collect_1688_full' THEN 'source_sku'
        WHEN 'fetch_freight'     THEN 'source_freight'
        WHEN 'inventory_sync'    THEN 'source_stock_change'
        WHEN 'alert_detect'      THEN 'source_alert_detect'
        WHEN 'sycm_snapshot'     THEN 'item_daily_sycm'
        ELSE dataset_code
    END
WHERE alert_type IN ('cron_skipped', 'cron_failed')
  AND dataset_code IS NULL
  AND old_value IN ('alimama_promo', 'collect_1688_full', 'fetch_freight',
                    'inventory_sync', 'alert_detect', 'sycm_snapshot');

-- 认出来的条数应为 0（跑过一遍后没有遗留）；非 0 说明有新增的 key 没进这张映射表，
-- 得回去在对应的 cron_*.sh 里补 --dataset，并把 key 加进上面的 CASE。
SELECT old_value, COUNT(*) AS still_null
FROM sync_alert
WHERE alert_type IN ('cron_skipped', 'cron_failed') AND dataset_code IS NULL
GROUP BY old_value;
