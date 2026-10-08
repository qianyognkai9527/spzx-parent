-- 推广计划主档（2026-10-08）
--
-- 为什么要新建一张：采集侧的 promo_cost_daily / promo_cost_item_daily 已经按计划维度落库
-- （唯一键里带 campaign_id），但「计划本身是什么」——预算、出价、时段、人群、谁负责、还在不在投——
-- 报表接口一个都不给（核过 raw_json 的 37 个键，全是效果指标）。所以主档是**录入处**，
-- 不是采集的镜像：能自动填的只有 id/名称/类型/出价方式这四样。
--
-- 三条口径写在这里，改表前先读：
-- 1. 计划↔宝贝 不建子表。promo_cost_item_daily 已经按 (campaign_id, item_id) 存了每天的实际投放主体，
--    再建一张关系表就是第二个真相源，两边一定会对不上。要查「这个计划投了哪些宝贝」，现算。
-- 2. 不存任何派生值（最后有花费的日期、累计花费、ROI）。这些一律读时从 cost 表算——
--    存下来必然滞后，而滞后的数字在界面上看起来像事实。
-- 3. online_status 允许 NULL 且含义是「未确认」。10-02 起这几个计划连续无投放，
--    但「无花费」不等于「停投」（可能是预算没花完、可能是报表滞后），所以不自动翻成 0，
--    由人在后台确认。页面必须把 NULL 显示成「未确认」，不许显示成「在投」。
--
-- 口令/密钥不落这张表：需要引用凭据时存 credential_ref（见 shop 表口径）。

CREATE TABLE IF NOT EXISTS `promo_plan` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `platform_code` tinyint NOT NULL DEFAULT 1 COMMENT '1=淘宝，与 promo_cost_daily 同枚举',
  `shop_id` bigint NOT NULL DEFAULT 0 COMMENT '店铺 id；0=未指定，与花费表同口径（不能为 NULL，否则唯一键失效）',
  `campaign_id` varchar(64) NOT NULL COMMENT '平台侧计划 id，自然键，采集与后台都按它对上',
  `campaign_name` varchar(255) NOT NULL COMMENT '最近已知名称；平台改名后以这里为准，历史花费行仍带旧名',
  `plan_type` varchar(16) NOT NULL DEFAULT 'other' COMMENT 'keyword=关键词推广(原直通车) crowd=人群推广(原引力魔方) site=全站推广 other',
  `bid_type` varchar(24) DEFAULT NULL COMMENT '接口 bidType：custom_bid≈标准计划 roi_control≈智能控投产；NULL=还没采到',
  `daily_budget` decimal(10,2) DEFAULT NULL COMMENT '日预算(元)，手录',
  `bid_price` decimal(10,4) DEFAULT NULL COMMENT '关键词/人群出价基准(元)，手录；与 /admin/kw/bid/calc 的关键词出价同口径',
  `premium_percent` int DEFAULT NULL COMMENT '人群溢价百分数，如 30 表示 +30%；NULL=未录',
  `time_discount` varchar(64) DEFAULT NULL COMMENT '分时折扣描述，如「00-08 不投，其余 100%」',
  `start_date` date DEFAULT NULL COMMENT '投放开始日',
  `end_date` date DEFAULT NULL COMMENT '投放结束日，空=长期',
  `online_status` tinyint DEFAULT NULL COMMENT 'NULL=未确认 0=停投 1=在投。采集侧只报「当天无投放数据」，不据此自动翻',
  `owner` varchar(32) DEFAULT NULL COMMENT '负责人',
  `remark` varchar(500) DEFAULT NULL,
  `source` varchar(16) NOT NULL DEFAULT 'manual' COMMENT 'manual=后台录入 collected=从花费数据自动登记',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_promo_plan_shop_campaign` (`platform_code`,`shop_id`,`campaign_id`),
  KEY `idx_promo_plan_status` (`platform_code`,`online_status`),
  KEY `idx_promo_plan_type` (`plan_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='推广计划主档：计划元数据的权威录入处，效果数据仍在 promo_cost_*_daily';

-- 从已有花费数据登记见过的计划（幂等，可反复跑）。
-- 名称/类型/出价方式取「最近一天的那行」，其余列一律留 NULL/默认，等人在后台确认。
-- online_status 故意不填：见文件头第 3 条。
INSERT INTO promo_plan
  (platform_code, shop_id, campaign_id, campaign_name, plan_type, bid_type, source)
SELECT platform_code, shop_id, campaign_id, campaign_name, plan_type, bid_type, 'collected'
FROM (
  SELECT platform_code, shop_id, campaign_id, campaign_name, plan_type, bid_type,
         ROW_NUMBER() OVER (PARTITION BY platform_code, shop_id, campaign_id
                            ORDER BY stat_date DESC, id DESC) AS rn
  FROM promo_cost_daily
  WHERE campaign_id <> ''
) t
WHERE rn = 1
ON DUPLICATE KEY UPDATE campaign_name = VALUES(campaign_name);

-- 删掉上游模板留下的六张壳表（2026-10-08 实测全部 0 行、无外键、无活引用）。
-- 结构备份在 dropped_plan_shells_20261008.sql，要恢复直接跑那个文件。
--   sys_plan / sys_plan_product：对应的 Java 代码已在 eda5f5a 删除；plan_id 是自增 id，
--     和平台 campaign_id 没有任何关系，硬接会变成两套计划 ID。
--   keyword_plan_product / _word / _crowd：AI 选词 spec 早写明「不复用现有空表 keyword_plan_*」。
--   oper_promotion_plan：只有 name/plan_type/market_target 四列，没有 campaign_id，接不上花费。
DROP TABLE IF EXISTS `sys_plan`;
DROP TABLE IF EXISTS `sys_plan_product`;
DROP TABLE IF EXISTS `keyword_plan_product`;
DROP TABLE IF EXISTS `keyword_plan_product_word`;
DROP TABLE IF EXISTS `keyword_plan_crowd`;
DROP TABLE IF EXISTS `oper_promotion_plan`;
