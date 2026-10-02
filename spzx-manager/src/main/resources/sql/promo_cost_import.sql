-- 淘宝付费推广日报表（关键词推广标准计划 + 人群推广标准计划）
--
-- 背景：ingest_dataset 里 id=7 早就登记了 promo_cost「推广花费」契约
-- （target_table=promo_cost_daily，required=campaign_id,stat_date，sla=30h，monitor=0），
-- 但目标表一直没建、没有任何写入方。这一节把它落地。
--
-- 2026-10-03 数据来源改向（重要）：万相台的报表导出实测拿不到，改成直接调它报表页自己的接口
-- （`campaign/horizontal/findPage.json` 带 rptQuery，一次返回区间内全部计划 + 指标；
--   指标字典在 `component/findList.json`，共 31 项）。采集方 `automation/tb-auto/collect_alimama_promo.py`。
-- 因此本文件第 3 节那张中文列名映射表（promo_import_map）**降级为 CSV 兜底路径**：
-- 走接口就不存在"猜中文列名"，字段名是接口契约，映射写在代码里。
-- 同一天删掉了 chat_count：万相台无界版不返回旺旺咨询量，留一列永远 NULL 是假数据源。
--
-- 与既有空表的关系（重要，别再走弯路）：
-- - sycm_sy_ztkb / sycm_sy_llkb：一天一行的**店铺级**宽表，字段里已有 keyword_fee/exact_crowd_fee/
--   full_site_fee 等花费拆分，但全仓 0 引用 0 写入，是上一套系统的遗骸。
-- - keyword_plan_* / oper_promotion_plan：计划**配置**（单元、关键词出价、人群溢价/规模），同样 0 引用；
--   AI 选词 spec 里已明确"不复用现有空表 keyword_plan_*"。
-- 这两类都答不了"哪个词/哪个人群在烧钱不出单"，所以新建 campaign/item 两级事实表，不去改那批遗骸。
--
-- 三条设计约束：
-- 1. 列名映射放在 promo_import_map 里当数据，不写死在解析器代码里（仅 CSV 路径需要）。
-- 2. 每一行原始数据整条留在 raw_json。映射以后怎么改，历史行都能重放，不用重新导出。
-- 3. 百分比一律按"百分数"存（ctr_percent=12.34 表示 12.34%）。接口给的是比值 0.1234，
--    入库前 ×100 —— 已实测 ctr = click/adPv，是比值不是百分数。
-- 4. 成交类指标有归因回补，同一 stat_date 的数字隔天会变 → 采集要滚动重拉，upsert 天然覆盖。

-- ============================================================================
-- 1. 计划粒度日报（= ingest_dataset 登记的 promo_cost_daily）
-- ============================================================================
CREATE TABLE IF NOT EXISTS promo_cost_daily
(
    id              BIGINT         NOT NULL AUTO_INCREMENT,
    shop_id         BIGINT         NOT NULL DEFAULT 0 COMMENT '店铺 id；导出报表通常不带店铺，0=导入时未指定（不能为 NULL，否则唯一键失效）',
    platform_code   TINYINT        NOT NULL DEFAULT 1 COMMENT '1=淘宝',
    stat_date       DATE           NOT NULL COMMENT '报表日期',
    plan_type       VARCHAR(16)    NOT NULL COMMENT 'keyword=关键词推广(原直通车) crowd=人群推广(原引力魔方) site=全站推广 other',
    campaign_id     VARCHAR(64)    NOT NULL COMMENT '计划 id',
    campaign_name   VARCHAR(255)   NULL,
    report_source   VARCHAR(64)    NOT NULL DEFAULT '' COMMENT '来源标识（导出入口/文件名），区分同一计划的不同版本报表',

    -- 投放侧
    charge          DECIMAL(12, 2) NULL COMMENT '花费(元)',
    ad_pv           BIGINT         NULL COMMENT '展现量',
    click           BIGINT         NULL COMMENT '点击量',
    ctr_percent     DECIMAL(10, 4) NULL COMMENT '点击率，按报表原样的百分数存：12.34 表示 12.34%',
    cpc             DECIMAL(10, 4) NULL COMMENT '平均点击花费(元)',
    cpm             DECIMAL(10, 4) NULL COMMENT '千次展现花费(元)',

    -- 成交侧。直接=通过广告点击直接成交，间接=点了之后别的路径成交，两者相加=总成交
    gmv_total       DECIMAL(12, 2) NULL COMMENT '总成交金额(元)',
    gmv_direct      DECIMAL(12, 2) NULL COMMENT '直接成交金额(元)',
    gmv_indirect    DECIMAL(12, 2) NULL COMMENT '间接成交金额(元)',
    order_total     INT            NULL COMMENT '总成交笔数',
    order_direct    INT            NULL COMMENT '直接成交笔数',
    roi             DECIMAL(10, 2) NULL COMMENT '投入产出比 = 总成交金额 / 花费，报表给什么存什么，不自己重算',

    -- 意向侧（转化漏斗中段，判断"有流量没成交"卡在哪一环）
    cart_count      INT            NULL COMMENT '总购物车数 cartInshopNum',
    item_collect    INT            NULL COMMENT '收藏宝贝数 itemColInshopNum',
    shop_collect    INT            NULL COMMENT '收藏店铺数 shopColDirNum',

    -- 2026-10-03 按阿里妈妈接口指标字典（component/findList.json 里页面渲染表头用的那 31 个）补齐。
    -- 原先建的 chat_count「旺旺咨询量」已删：字典里根本没有这个指标，万相台无界版不返回，
    -- 留一列永远 NULL 比留空更糟——看着有数据源，实际是假的。
    -- 口径与已验证的四条一致：*_percent 一律 ×100 后的百分数（接口给比值），
    -- 笔数/件数用 INT，成本类 DECIMAL(10,2)，购物金 DECIMAL(12,2)。
    order_indirect             INT            NULL COMMENT '间接成交笔数 alipayIndirNum',
    cvr_percent                DECIMAL(10, 4) NULL COMMENT '点击转化率 cvr，百分数',
    order_cost                 DECIMAL(10, 2) NULL COMMENT '总成交成本 alipayInshopCost',
    cart_direct                INT            NULL COMMENT '直接购物车数 cartDirNum',
    cart_indirect              INT            NULL COMMENT '间接购物车数 cartIndirNum',
    cart_rate_percent          DECIMAL(10, 4) NULL COMMENT '加购率 cartRate，百分数',
    cart_cost                  DECIMAL(10, 2) NULL COMMENT '加购成本 cartCost',
    collect_total              INT            NULL COMMENT '总收藏数 colNum（= 收藏宝贝 + 收藏店铺，已实测）',
    item_collect_rate_percent  DECIMAL(10, 4) NULL COMMENT '宝贝收藏率 itemColInshopRate，百分数',
    item_collect_cost          DECIMAL(10, 2) NULL COMMENT '宝贝收藏成本 itemColInshopCost',
    shop_collect_cost          DECIMAL(10, 2) NULL COMMENT '店铺收藏成本 shopColInshopCost',
    collect_cart_total         INT            NULL COMMENT '总收藏加购数 colCartNum',
    collect_cart_cost          DECIMAL(10, 2) NULL COMMENT '总收藏加购成本 colCartCost',
    item_collect_cart          INT            NULL COMMENT '宝贝收藏加购数 itemColCart',
    item_collect_cart_cost     DECIMAL(10, 2) NULL COMMENT '宝贝收藏加购成本 itemColCartCost',
    shopping_amt               DECIMAL(12, 2) NULL COMMENT '购物金充值金额 shoppingAmt',
    add_new_uv                 INT            NULL COMMENT '新增客数 addNewUv（人群推广返回，指标字典里没有）',

    -- 计划属性，非指标：「标准计划」与「智能计划」的判据
    bid_type                   VARCHAR(24)    NULL COMMENT '接口 bidType：custom_bid≈标准计划 roi_control≈智能控投产。采集按它筛标准计划',

    raw_json        TEXT           NULL COMMENT '整行原始键值 JSON：映射改动后可重放，不必重新导出',
    import_batch    VARCHAR(64)    NULL COMMENT '导入批次号，配合整批回滚',
    create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    -- 契约里的自然键是 shop_id,campaign_id,stat_date；这里必须再加 plan_type：
    -- 关键词报表与人群报表是两份导出，同一天的同一计划可能各出一行，且 shop_id 允许 0。
    UNIQUE KEY uk_promo_daily (shop_id, plan_type, campaign_id, stat_date),
    KEY idx_promo_daily_date (stat_date),
    KEY idx_promo_daily_campaign (campaign_id)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci COMMENT ='付费推广计划粒度日报';

-- ============================================================================
-- 2. 明细粒度日报：关键词 / 人群 / 创意 / 宝贝 / 地域
--    宝贝维度（dimension='item'）是这一整套的最终目的：
--    只有推广花费落到商品上，商品运营台的毛利才能扣掉推广费，算出真实 ROI。
-- ============================================================================
CREATE TABLE IF NOT EXISTS promo_cost_item_daily
(
    id              BIGINT         NOT NULL AUTO_INCREMENT,
    shop_id         BIGINT         NOT NULL DEFAULT 0,
    platform_code   TINYINT        NOT NULL DEFAULT 1,
    stat_date       DATE           NOT NULL,
    plan_type       VARCHAR(16)    NOT NULL COMMENT 'keyword|crowd|site|other',
    dimension       VARCHAR(16)    NOT NULL COMMENT '明细维度：keyword|crowd|creative|item|region|unit',
    entity_key      VARCHAR(191)   NOT NULL COMMENT '明细标识：有 id 用 id，没有则用名称（关键词本身没有 id）',
    entity_id       VARCHAR(64)    NULL,
    entity_name     VARCHAR(255)   NULL COMMENT '关键词文本 / 人群名 / 创意名 / 商品标题',
    -- 关键词/人群维度的报表行本身还带着"这条投在哪个宝贝上"，那是把推广费摊到商品的唯一桥梁，
    -- 必须和 entity_* 分开存：合成一个字段的话，要么关键词文本被宝贝 id 顶掉，要么 dimension 认不出来
    item_id         VARCHAR(64)    NULL COMMENT '该明细所属宝贝 id，与 platform_product.code 对得上',
    item_name       VARCHAR(255)   NULL COMMENT '该明细所属宝贝标题',
    campaign_id     VARCHAR(64)    NOT NULL DEFAULT '' COMMENT '所属计划；明细报表不带计划列时留空串（唯一键里的列不能为 NULL，NULL 之间不算重复，重导会堆重复行）',
    campaign_name   VARCHAR(255)   NULL,
    unit_id         VARCHAR(64)    NULL COMMENT '单元 id（直通车有单元层）',
    unit_name       VARCHAR(255)   NULL,
    report_source   VARCHAR(64)    NOT NULL DEFAULT '',

    charge          DECIMAL(12, 2) NULL,
    ad_pv           BIGINT         NULL,
    click           BIGINT         NULL,
    ctr_percent     DECIMAL(10, 4) NULL,
    cpc             DECIMAL(10, 4) NULL,
    gmv_total       DECIMAL(12, 2) NULL,
    gmv_direct      DECIMAL(12, 2) NULL,
    gmv_indirect    DECIMAL(12, 2) NULL,
    order_total     INT            NULL,
    roi             DECIMAL(10, 2) NULL,
    cart_count      INT            NULL,
    item_collect    INT            NULL,

    raw_json        TEXT           NULL,
    import_batch    VARCHAR(64)    NULL,
    create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_promo_item (shop_id, dimension, entity_key, campaign_id, stat_date),
    KEY idx_promo_item_date (stat_date),
    KEY idx_promo_item_entity (entity_key),
    KEY idx_promo_item_dim (dimension, stat_date)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci COMMENT ='付费推广明细粒度日报（关键词/人群/创意/宝贝/地域）';

-- ============================================================================
-- 3. 列名映射：报表原始列名 → 目标字段。这是"没见过真实导出文件"这个信息缺口的存放处
-- ============================================================================
CREATE TABLE IF NOT EXISTS promo_import_map
(
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    report_level  VARCHAR(16)  NOT NULL COMMENT 'campaign=计划日报 item=明细日报（决定写进哪张事实表）',
    source_column VARCHAR(128) NOT NULL COMMENT 'CSV 原始列名，比对前会去空格',
    target_column VARCHAR(64)  NOT NULL COMMENT '事实表字段名（白名单，解析器只认它认识的字段）',
    verified      TINYINT      NOT NULL DEFAULT 0 COMMENT '1=已用真实导出文件核对过；0=按常见报表字段预置，待核对',
    status        TINYINT      NOT NULL DEFAULT 1,
    remark        VARCHAR(255) NULL,
    create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_promo_map (report_level, source_column)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci COMMENT ='推广报表列名映射';

-- 预置映射：按阿里妈妈系报表的常见中文列名铺一遍，全部 verified=0。
-- 今晚第一次导入时，未命中的列会被接口原样报出来，届时补映射即可，不用改代码。
INSERT IGNORE INTO promo_import_map (report_level, source_column, target_column, verified, remark)
VALUES ('campaign', '日期', 'stat_date', 0, '待核对'),
       ('campaign', '报表日期', 'stat_date', 0, NULL),
       ('campaign', '计划ID', 'campaign_id', 0, NULL),
       ('campaign', '计划名称', 'campaign_name', 0, NULL),
       ('campaign', '花费', 'charge', 0, NULL),
       ('campaign', '总消耗', 'charge', 0, '部分报表叫总消耗'),
       ('campaign', '展现量', 'ad_pv', 0, NULL),
       ('campaign', '曝光量', 'ad_pv', 0, NULL),
       ('campaign', '点击量', 'click', 0, NULL),
       ('campaign', '点击', 'click', 0, NULL),
       ('campaign', '点击率', 'ctr_percent', 0, '百分数原样存'),
       ('campaign', '平均点击花费', 'cpc', 0, NULL),
       ('campaign', '千次展现花费', 'cpm', 0, NULL),
       ('campaign', '总成交金额', 'gmv_total', 0, NULL),
       ('campaign', '成交金额', 'gmv_total', 0, NULL),
       ('campaign', '直接成交金额', 'gmv_direct', 0, NULL),
       ('campaign', '间接成交金额', 'gmv_indirect', 0, NULL),
       ('campaign', '总成交笔数', 'order_total', 0, NULL),
       ('campaign', '直接成交笔数', 'order_direct', 0, NULL),
       ('campaign', '投入产出比', 'roi', 0, NULL),
       ('campaign', 'ROI', 'roi', 0, NULL),
       ('campaign', '加入购物车数', 'cart_count', 0, NULL),
       ('campaign', '加购数', 'cart_count', 0, NULL),
       ('campaign', '收藏商品数', 'item_collect', 0, NULL),
       ('campaign', '收藏店铺数', 'shop_collect', 0, NULL),
       ('campaign', '单元ID', 'unit_id', 0, '计划级报表里出现说明是单元维度，导入会降级到明细表'),
       ('campaign', '单元名称', 'unit_name', 0, NULL),
       ('item', '日期', 'stat_date', 0, NULL),
       ('item', '关键词', 'entity_keyword', 0, '关键词没有 id，用文本当 entity_key'),
       ('item', '人群名称', 'entity_crowd', 0, NULL),
       ('item', '创意名称', 'entity_creative', 0, NULL),
       ('item', '宝贝名称', 'item_name', 0, '关键词行里的所属宝贝，不是明细本身'),
       ('item', '商品名称', 'item_name', 0, NULL),
       ('item', '推广单元', 'unit_name', 0, NULL),
       ('item', '计划ID', 'campaign_id', 0, NULL),
       ('item', '计划名称', 'campaign_name', 0, NULL),
       ('item', '主体ID', 'entity_id', 0, '创意等维度的主体 id'),
       ('item', '宝贝ID', 'item_id', 0, '与 platform_product.code 对得上，是算真实 ROI 的桥'),
       ('item', '商品ID', 'item_id', 0, NULL),
       ('item', '花费', 'charge', 0, NULL),
       ('item', '展现量', 'ad_pv', 0, NULL),
       ('item', '点击量', 'click', 0, NULL),
       ('item', '点击率', 'ctr_percent', 0, NULL),
       ('item', '平均点击花费', 'cpc', 0, NULL),
       ('item', '总成交金额', 'gmv_total', 0, NULL),
       ('item', '直接成交金额', 'gmv_direct', 0, NULL),
       ('item', '投入产出比', 'roi', 0, NULL),
       ('item', '加入购物车数', 'cart_count', 0, NULL);

-- ============================================================================
-- 4. 契约登记：promo_cost 的目标表已经建了，把 remark 改掉并补一条明细数据集
--    monitor 先保持 0 —— 在第一次成功导入之前开监控只会产生一条必然过期的告警（§24 那条 bootstrap 规则）
-- ============================================================================
UPDATE ingest_dataset
SET target_table  = 'promo_cost_daily',
    natural_key_cols = 'shop_id,plan_type,campaign_id,stat_date',
    remark        = '目标表已建（promo_cost_daily / promo_cost_item_daily）。首次成功导入后再开 monitor',
    update_time   = NOW()
WHERE code = 'promo_cost';

INSERT IGNORE INTO ingest_dataset (code, name, platform_code, measure, target_table, natural_key_cols,
                                   required_cols, sla_hours, monitor, writer, cron_expr, remark)
VALUES ('promo_cost_detail', '推广明细日报', 1, 'batch', 'promo_cost_item_daily',
        'shop_id,dimension,entity_key,campaign_id,stat_date', 'stat_date,dimension,entity_key', 48, 0,
        'java:PromoCostService#importCsv', NULL,
        '关键词/人群/宝贝维度明细。宝贝维度用于把推广费摊到商品上算真实 ROI');

-- ============================================================================
-- 自检
-- ============================================================================
SELECT table_name, table_rows
FROM information_schema.tables
WHERE table_schema = 'db_spzx'
  AND table_name IN ('promo_cost_daily', 'promo_cost_item_daily', 'promo_import_map');

SELECT report_level, COUNT(*) AS mappings, SUM(verified = 0) AS need_verify
FROM promo_import_map
GROUP BY report_level;

SELECT code, name, measure, target_table, natural_key_cols, sla_hours, monitor
FROM ingest_dataset
WHERE code IN ('promo_cost', 'promo_cost_detail');
