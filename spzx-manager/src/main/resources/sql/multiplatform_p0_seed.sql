-- P0 数据：平台/店铺/能力矩阵种子 + shop_id 回填
-- 必须用 utf8mb4 客户端执行，否则本机的 character_set_client=latin1 会把中文双重编码：
--   mysql --default-character-set=utf8mb4 -D db_spzx < multiplatform_p0_seed.sql
-- 店铺 id 显式指定，保证脚本可重复执行且 platform_product.shop_id 等外键值稳定。

INSERT INTO platform (code, slug, name, theme_color, money_channel, enabled)
VALUES (1, 'taobao', '淘宝', '#ff6600', 'alipay', 1),
       (2, 'douyin', '抖音', '#00d4ff', 'platform_settlement', 1),
       (3, 'pinduoduo', '拼多多', '#e02e2e', 'platform_settlement', 0)
ON DUPLICATE KEY UPDATE name        = VALUES(name),
                        theme_color = VALUES(theme_color),
                        money_channel = VALUES(money_channel);

INSERT INTO shop (id, platform_code, shop_name, ingest_channel, is_default, status)
VALUES (1, 1, '淘宝默认店', 'browser', 1, 1),
       (2, 2, '抖音默认店', 'browser', 1, 1),
       (3, 3, '拼多多默认店', 'browser', 1, 0)
ON DUPLICATE KEY UPDATE shop_name  = VALUES(shop_name),
                        is_default = VALUES(is_default),
                        status     = VALUES(status);

INSERT INTO platform_capability (platform_code, capability, supported, note)
VALUES (1, 'ingest_order', 1, 'order_info 由自动化写入'),
       (1, 'ingest_item', 1, 'platform_product'),
       (1, 'ingest_item_daily', 1, 'sycm_item_effect_history，P2 迁标准表'),
       (1, 'ingest_promo_cost', 0, '淘宝推广数据未接入'),
       (1, 'publish_product', 1, 'tb-auto 铺货'),
       (1, 'attach_media', 1, 'product_media'),
       (2, 'ingest_order', 1, 'crawl_douyin_orders'),
       (2, 'ingest_item', 1, 'create_douyin_product'),
       (2, 'ingest_item_daily', 0, '抖店流量数据未接入'),
       (2, 'ingest_promo_cost', 0, '千川未接入'),
       (2, 'publish_product', 1, '抖店直建'),
       (2, 'attach_media', 1, 'product_media'),
       (3, 'ingest_order', 0, '店铺未起，P1 接入'),
       (3, 'ingest_after_sale', 0, 'P1'),
       (3, 'ingest_item', 0, 'P1'),
       (3, 'ingest_item_daily', 0, 'P1'),
       (3, 'ingest_promo_cost', 0, 'P1'),
       (3, 'publish_product', 0, '本期不做写动作'),
       (3, 'attach_media', 0, '本期不做写动作')
ON DUPLICATE KEY UPDATE supported = VALUES(supported),
                        note      = VALUES(note);

-- ============ shop_id 回填：历史行一律指向该平台的默认店 ============
-- 源头从未记录店铺，不做任何"还原真实店铺"的尝试。
-- 订单与退款三张表的历史行 platform_type 为 NULL，归属未知，这里不写入。

UPDATE platform_product pp
  JOIN shop s ON s.platform_code = pp.platform_type AND s.is_default = 1
   SET pp.shop_id = s.id
 WHERE pp.shop_id IS NULL OR pp.shop_id <> s.id;

UPDATE order_info o
  JOIN shop s ON s.platform_code = o.platform_type AND s.is_default = 1
   SET o.shop_id = s.id
 WHERE o.shop_id IS NULL OR o.shop_id <> s.id;

UPDATE refund_import_order r
  JOIN shop s ON s.platform_code = r.platform_type AND s.is_default = 1
   SET r.shop_id = s.id
 WHERE r.shop_id IS NULL OR r.shop_id <> s.id;

UPDATE refund_analysis_report r
  JOIN shop s ON s.platform_code = r.platform_type AND s.is_default = 1
   SET r.shop_id = s.id
 WHERE r.shop_id IS NULL OR r.shop_id <> s.id;

UPDATE refund_analysis_detail d
  JOIN shop s ON s.platform_code = d.platform_type AND s.is_default = 1
   SET d.shop_id = s.id
 WHERE d.shop_id IS NULL OR d.shop_id <> s.id;

-- sync_alert 没有 platform_type，店铺归属经由关联的平台商品派生
UPDATE sync_alert sa
  JOIN platform_product pp ON sa.platform_product_id = pp.id AND pp.shop_id IS NOT NULL
   SET sa.shop_id = pp.shop_id
 WHERE sa.shop_id IS NULL OR sa.shop_id <> pp.shop_id;
