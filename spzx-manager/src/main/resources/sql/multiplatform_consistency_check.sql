-- 平台/店铺归属一致性巡检（D9 的落地件：冗余 platform_type 保留，用巡检锁住漂移）
--
-- 为什么需要：库里 41 张表带 platform_type，只有 6 张带 shop_id。子表的平台值是各自
-- 写入方（Java 各 service + automation/ 下 11 个 Python 直写脚本）自己填的，
-- 没有外键、没有触发器，父子不一致只会在报表口径上慢慢显形。
-- D9 决定「保留冗余列 + 加一致性校验」，本文件就是那条校验：每条 SELECT 都应返回 0 行。
--
-- 执行：mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < multiplatform_consistency_check.sql
-- 只读，不改数据。发现违规时按规则号回来补 CASE 说明。

-- R1 子表 platform_type 与其父 platform_product 不一致（链接列 product_id / platform_product_id）
SELECT 'R1 order_source_relation' rule, COUNT(*) bad FROM order_source_relation c
  JOIN platform_product p ON p.id = c.platform_product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 product_media', COUNT(*) FROM product_media c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 platform_product_sku', COUNT(*) FROM platform_product_sku c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 platform_product_title', COUNT(*) FROM platform_product_title c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 product_details', COUNT(*) FROM product_details c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 kw_product_analysis', COUNT(*) FROM kw_product_analysis c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type
UNION ALL
SELECT 'R1 brush_order', COUNT(*) FROM brush_order c
  JOIN platform_product p ON p.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND c.platform_type <> p.platform_type;

-- R1 不含 product_source_link：它的 product_id 存的是 source_product.id（见 automation/sourcing/_archive_20260906/sync_isv_to_platform.py:5），
-- 且该列是 varchar，与 source_product.id(44~7677) / platform_product.id(38~4722) 两个区间都重叠，
-- 误当平台商品来 join 会"匹配成功"并产出 673 行假违规。这类 varchar 外键不要拿来推断归属。

-- R2 批次/明细跟随所属报表：refund_import_order 按 order_data_code、detail 按 record_id
SELECT 'R2 refund_import_order' rule, COUNT(*) bad FROM refund_import_order r
  JOIN refund_analysis_report p ON p.order_data_code = r.code
 WHERE r.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND r.platform_type <> p.platform_type
UNION ALL
SELECT 'R2 refund_analysis_detail', COUNT(*) FROM refund_analysis_detail d
  JOIN refund_analysis_report p ON p.id = d.record_id
 WHERE d.platform_type IS NOT NULL AND p.platform_type IS NOT NULL AND d.platform_type <> p.platform_type;

-- R3 shop_id 与 platform_type 指向不同平台（shop.platform_code 是店铺归属的唯一权威）
SELECT 'R3 order_info' rule, COUNT(*) bad FROM order_info t JOIN shop s ON s.id = t.shop_id
 WHERE t.shop_id IS NOT NULL AND t.platform_type IS NOT NULL AND s.platform_code <> t.platform_type
UNION ALL SELECT 'R3 platform_product', COUNT(*) FROM platform_product t JOIN shop s ON s.id = t.shop_id
 WHERE t.shop_id IS NOT NULL AND t.platform_type IS NOT NULL AND s.platform_code <> t.platform_type
UNION ALL SELECT 'R3 refund_import_order', COUNT(*) FROM refund_import_order t JOIN shop s ON s.id = t.shop_id
 WHERE t.shop_id IS NOT NULL AND t.platform_type IS NOT NULL AND s.platform_code <> t.platform_type
UNION ALL SELECT 'R3 refund_analysis_report', COUNT(*) FROM refund_analysis_report t JOIN shop s ON s.id = t.shop_id
 WHERE t.shop_id IS NOT NULL AND t.platform_type IS NOT NULL AND s.platform_code <> t.platform_type
UNION ALL SELECT 'R3 refund_analysis_detail', COUNT(*) FROM refund_analysis_detail t JOIN shop s ON s.id = t.shop_id
 WHERE t.shop_id IS NOT NULL AND t.platform_type IS NOT NULL AND s.platform_code <> t.platform_type;

-- R4 shop_id 指向不存在或平台已注销的店铺（回填脚本改过 shop.id 后会出这种悬空）
-- COALESCE 是必需的：空表或全 NULL 时 SUM() 返回 NULL，不是 0
SELECT 'R4 悬空 shop_id' rule, COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) bad
  FROM order_info
UNION ALL SELECT 'R4 悬空 shop_id', COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) FROM platform_product
UNION ALL SELECT 'R4 悬空 shop_id', COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) FROM refund_import_order
UNION ALL SELECT 'R4 悬空 shop_id', COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) FROM refund_analysis_report
UNION ALL SELECT 'R4 悬空 shop_id', COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) FROM refund_analysis_detail
UNION ALL SELECT 'R4 悬空 shop_id', COALESCE(SUM(shop_id IS NOT NULL AND shop_id NOT IN (SELECT id FROM shop)), 0) FROM sync_alert;

-- R5 platform_type 取值必须在 platform 注册表里（防止出现代码里没登记的 4/5）
SELECT 'R5 未注册平台码' rule, COUNT(DISTINCT t.platform_type) bad
  FROM (SELECT platform_type FROM order_info UNION ALL SELECT platform_type FROM platform_product
        UNION ALL SELECT platform_type FROM refund_import_order UNION ALL SELECT platform_type FROM product_media
        UNION ALL SELECT platform_type FROM order_source_relation) t
 WHERE t.platform_type IS NOT NULL AND t.platform_type NOT IN (SELECT code FROM platform);

-- R6 sync_alert 由商品派生店铺：告警带 shop_id 时，必须与其 platform_product 的 shop_id 一致
SELECT 'R6 sync_alert 店铺漂移' rule, COUNT(*) bad FROM sync_alert a
  JOIN platform_product p ON p.id = a.platform_product_id
 WHERE a.shop_id IS NOT NULL AND p.shop_id IS NOT NULL AND a.shop_id <> p.shop_id;

-- ===== 以下是告警级（已知遗留，允许非 0，但每次跑都要看数字有没有变大）=====

-- W1 product_source_link 的平台列与它的真实父行 source_product 不一致。
-- 现状：673 行全写死 platform_type=2(抖音)，而其货源行是 535 淘宝 + 138 抖音 → 535 不一致。
-- 写入方 automation/sourcing/_archive_20260906/sync_isv_to_platform.py 已归档，活跃脚本无人再写这张表，
-- 所以这是一份陈旧遗留而不是持续产生的脏数据。定性前不要批量 UPDATE：这张表被 Java 的
-- MallProductLinkController 读写，页面口径可能也按"抖音"在用。要修就连带确认读取方。
SELECT 'W1 product_source_link 平台列(已知遗留)' rule, COUNT(*) bad
  FROM product_source_link c JOIN source_product s ON s.id = c.product_id
 WHERE c.platform_type IS NOT NULL AND s.platform_type IS NOT NULL AND c.platform_type <> s.platform_type;
