-- 历史订单/售后数据的平台归属回填（2026-09-29，业务确认：均为淘宝默认店）
--
-- 背景：platform_type 由 sql/add_platform_type.sql 后加，只加列没回填；
--       shop_id 由 sql/multiplatform_p0.sql 后加，P0 种子脚本的回填依赖 platform_type，
--       因此这两批行的 shop_id 也一直是 NULL。
--
-- 可交叉验证的归属依据：无。已逐一确认——
--   order_info(43) 与 order_source_relation 按 order_no 关联命中 0 行；
--   refund_import_order.code 是报表批次码（雪花 id，与 refund_analysis_report.order_data_code 对应，
--     4 个批次 = 31+47+45+96 = 219 行），与 platform_product.code 命中 0 行；
--   order_bind 为空表。
--   所以这里的归属来自业务口头确认，而不是数据推导。若日后发现有抖音单混在
--   order_info 里，按 order_no 白名单单独改成 2 并换 shop_id 即可（脚本可重跑）。
--
-- 执行：mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < backfill_platform_type_taobao.sql
-- 只写 platform_type / shop_id 两列，可重复执行（WHERE 限定 IS NULL）。

-- 前置快照（与 sql/multiplatform_p0_verify.sql 同口径，用于事后对账）
SELECT 'order_info' t, COUNT(*) rows_, SUM(total_amount) money FROM order_info
UNION ALL SELECT 'refund_import_order', COUNT(*), SUM(refund_money) FROM refund_import_order
UNION ALL SELECT 'refund_analysis_report', COUNT(*), SUM(total_amount) FROM refund_analysis_report
UNION ALL SELECT 'refund_analysis_detail', COUNT(*), NULL FROM refund_analysis_detail;

UPDATE order_info
   SET platform_type = 1, shop_id = 1
 WHERE platform_type IS NULL;

UPDATE refund_analysis_report
   SET platform_type = 1, shop_id = 1
 WHERE platform_type IS NULL;

-- 明细批次跟随其所属报表，避免两张表口径漂移
UPDATE refund_import_order r
  JOIN refund_analysis_report p ON p.order_data_code = r.code
   SET r.platform_type = p.platform_type, r.shop_id = p.shop_id
 WHERE r.platform_type IS NULL AND p.platform_type IS NOT NULL;

-- 兜底：没有对应报表的孤儿批次行（当前 0 行）
UPDATE refund_import_order
   SET platform_type = 1, shop_id = 1
 WHERE platform_type IS NULL;

UPDATE refund_analysis_detail d
  JOIN refund_analysis_report p ON p.id = d.record_id
   SET d.platform_type = p.platform_type, d.shop_id = p.shop_id
 WHERE d.platform_type IS NULL AND p.platform_type IS NOT NULL;

UPDATE refund_analysis_detail
   SET platform_type = 1, shop_id = 1
 WHERE platform_type IS NULL;

-- 结果快照
SELECT 'order_info' t, COUNT(*) rows_, SUM(total_amount) money,
       SUM(platform_type = 1) taobao, SUM(shop_id = 1) shop1 FROM order_info
UNION ALL SELECT 'refund_import_order', COUNT(*), SUM(refund_money),
       SUM(platform_type = 1), SUM(shop_id = 1) FROM refund_import_order
UNION ALL SELECT 'refund_analysis_report', COUNT(*), SUM(total_amount),
       SUM(platform_type = 1), SUM(shop_id = 1) FROM refund_analysis_report
UNION ALL SELECT 'refund_analysis_detail', COUNT(*), NULL,
       SUM(platform_type = 1), SUM(shop_id = 1) FROM refund_analysis_detail;
