-- 采集契约 P1a：ingest_dataset / ingest_batch / ingest_raw（DDL + 种子）
-- 依据 docs/superpowers/specs/2026-09-29-multiplatform-ingest-design.md 第 6/8 节
--
-- 本机 character_set_client 默认 latin1，必须带 utf8mb4 否则中文注释双重编码：
--   mysql --defaults-extra-file=/tmp/spzx_my.cnf --default-character-set=utf8mb4 -D db_spzx < ingest_contract_p1a.sql
-- 对账：ingest_contract_p1a_verify.sql
-- CREATE TABLE IF NOT EXISTS 可重复执行；种子用 INSERT IGNORE，重复执行不改已有行。

-- ============ 契约元数据 + 新鲜度状态（Java 侧拥有，见 IngestFreshnessService） ============
CREATE TABLE IF NOT EXISTS ingest_dataset (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  code           VARCHAR(32)  NOT NULL COMMENT '数据集编码，全局唯一，与 Python datasets.json 对齐',
  name           VARCHAR(64)  NOT NULL COMMENT '展示名',
  platform_code  TINYINT      NULL COMMENT '归属平台码，NULL=跨平台上游(1688货源)；不加外键，registry 是 TINYINT 主键且会变',
  measure        VARCHAR(16)  NOT NULL DEFAULT 'table' COMMENT '新鲜度取值方式 table=读事实表时间列 batch=读 ingest_batch 成功时间',
  target_table   VARCHAR(64)  NULL COMMENT 'measure=table 时的事实表；必须选 Java 不会写的那张，否则后台改一行数据就会伪装成"刚采过"',
  freshness_col  VARCHAR(64)  NULL COMMENT 'measure=table 时代表采集时刻的列',
  natural_key_cols VARCHAR(128) NULL COMMENT '洗数去重自然键，逗号分隔',
  required_cols  VARCHAR(255) NULL COMMENT '洗数必填列，缺失即标 invalid',
  sla_hours      INT          NOT NULL DEFAULT 48 COMMENT '超过多少小时没有成功写入即判过期，按该数据集真实调度周期留冗余',
  monitor        TINYINT      NOT NULL DEFAULT 0 COMMENT '0=契约已登记但当前无自动写入方，不参与告警；1=纳入新鲜度告警',
  writer         VARCHAR(128) NULL COMMENT '当前写入方(脚本或通道)，排障用',
  cron_expr      VARCHAR(32)  NULL COMMENT '调度表达式快照，仅展示与推算 SLA 用，Java 不据此调度',
  stale_since    DATETIME     NULL COMMENT '本轮过期起点，恢复新鲜后置 NULL',
  alerted_at     DATETIME     NULL COMMENT '本轮过期已推送告警的时间，与 stale_since 比较实现一轮只告一次',
  remark         VARCHAR(255) NULL,
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ingest_dataset_code (code),
  KEY idx_ingest_dataset_monitor (monitor, code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '采集数据集契约与新鲜度状态';

-- ============ 批次（Python 唯一的批次写入点） ============
CREATE TABLE IF NOT EXISTS ingest_batch (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  -- 与 ingest_dataset.platform_code 同口径：1688 货源侧采集（collect_1688_full/fetch_freight/
  -- detect_stock_change）是跨平台复用的上游数据，定不出平台。原先 NOT NULL 会逼出一个假平台码。
  platform_code  TINYINT      NULL COMMENT '归属平台码，NULL=跨平台上游(1688货源)',
  shop_id        BIGINT       NULL COMMENT '店铺，采集时无法定店则留空，由洗数补齐',
  dataset        VARCHAR(32)  NOT NULL COMMENT 'ingest_dataset.code',
  channel        VARCHAR(16)  NOT NULL DEFAULT 'browser' COMMENT 'api|browser|export|derived(库内派生重算,不采新数据)',
  biz_from       DATE         NULL COMMENT '业务时间窗起，非抓取时间',
  biz_to         DATE         NULL COMMENT '业务时间窗止；窗口重叠是设计意图(防漏)，重复由自然键消化',
  rows_total     INT          NOT NULL DEFAULT 0,
  rows_ok        INT          NOT NULL DEFAULT 0,
  rows_dup       INT          NOT NULL DEFAULT 0,
  rows_invalid   INT          NOT NULL DEFAULT 0,
  status         VARCHAR(16)  NOT NULL DEFAULT 'queued' COMMENT 'queued|running|success|partial|failed',
  fingerprint    CHAR(32)     NULL COMMENT 'shop+dataset+窗口+来源指纹，Python 建批幂等键',
  error          TEXT         NULL,
  started_at     DATETIME     NULL,
  finished_at    DATETIME     NULL,
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_batch_fingerprint (fingerprint),
  KEY idx_batch_dataset_status (dataset, status, finished_at),
  KEY idx_batch_shop (platform_code, shop_id),
  CONSTRAINT ck_batch_status CHECK (status IN ('queued', 'running', 'success', 'partial', 'failed'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '采集批次台账';

-- ============ 原始报文（洗数前留档，平台改字段时改映射器重放即可，不必重抓） ============
CREATE TABLE IF NOT EXISTS ingest_raw (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  batch_id     BIGINT       NOT NULL,
  natural_key  VARCHAR(128) NOT NULL COMMENT '该数据集的自然键值，按 natural_key_cols 拼接',
  payload      JSON         NOT NULL,
  fingerprint  CHAR(32)     NULL,
  status       VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending|normalized|invalid',
  error        VARCHAR(512) NULL,
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_raw_batch_key (batch_id, natural_key),
  KEY idx_raw_pending (status, id),
  KEY idx_raw_fingerprint (fingerprint),
  CONSTRAINT ck_raw_status CHECK (status IN ('pending', 'normalized', 'invalid'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '采集原始报文';

-- ============ 种子 ============
-- monitor=1 的判据（三条同时成立，缺一条就置 0，否则告警要么永不误报、要么永远在叫）：
--   1) 有 cron/定时调度在跑；2) 每次成功运行都会无条件写入（不是"有变化才写"的事件表）；
--   3) 时间列只有 Python 写、Java 不写（Java 侧任何 UPDATE 都会把 update_time 顶成"新鲜"）。
-- 2026-09-29 实测：sycm 快照 6 点定时插入整批；source_sku 每周六全量重写全部行（09-12/09-19 两轮静默未跑）。
-- Java 对这两张表只有 SELECT，无写入路径。
INSERT IGNORE INTO ingest_dataset
  (code, name, platform_code, measure, target_table, freshness_col,
   natural_key_cols, required_cols, sla_hours, monitor, writer, cron_expr, remark)
VALUES
  ('item_daily_sycm', '淘宝商品日效果快照', 1, 'table', 'sycm_item_effect_history', 'snapshot_time',
   'shop_id,item_id,stat_date', 'item_id,stat_date', 30, 1,
   'automation/sourcing/sycm_item_snapshot.py', '0 6 * * *',
   'Chrome 9222 不在线时 cron_sycm_snapshot.sh 直接 exit 0 静默跳过，后台原本无感知，故纳入告警；9222 需人工在线'),
  ('source_sku', '1688 货源 SKU 快照', NULL, 'table', 'source_sku', 'update_time',
   'source_product_id,sku_key', 'source_product_id,sku_key,price', 192, 1,
   'automation/sourcing/collect_1688_full.py', '0 3 * * 6',
   '每周六全量重写；SLA 按周留 8 天冗余，周末机器不开机不至于天天告警'),
  -- P1b 起这两个数据集有真实批次写入方（cron_batch.py 由 wrapper 每轮记一行），
  -- measure=batch 的判据从此可用，故 monitor=1
  ('source_freight', '1688 运费补抓', NULL, 'batch', 'source_product', NULL,
   'source_product_id', 'freight_cost', 192, 1,
   'automation/sourcing/fetch_freight.py', '30 3 * * 6',
   '事实是"缺口在缩"，无独立时间列（source_product.update_time 被 Java 编辑顶掉），故按批次判新鲜'),
  ('source_stock_change', '货源库存变动检测', NULL, 'batch', 'inventory_change_log', NULL,
   'source_sku_id,detect_date', 'source_sku_id', 48, 1,
   'automation/sourcing/detect_stock_change.py', '0 5 * * *',
   'inventory_change_log 是"有变化才写"的事件表，不能当心跳；用 wrapper 每轮落的批次判据'),
  -- 同一条 cron 里的第二段命令，此前共用第一段的 rc：detect_alerts 跑挂也记 success
  ('source_alert_detect', '货源下架与变价提醒检测', NULL, 'batch', 'sync_alert', NULL,
   'alert_type,source_product_id', 'alert_type,message', 30, 1,
   'automation/sourcing/detect_alerts.py', '0 5 * * *',
   'product_down/sku_down/price_change 三类提醒的唯一生产者，停摆=货源下架了后台也不出声。行数=本轮新增提醒条数，0 是常态(没检出问题)，故障信号看 status 不是看行数'),
  -- crontab 这一行是 `python grade_quality.py` 直调，没有 bash 包装层，台账由脚本自己 import 写
  ('source_quality_grade', '货源质量分级重算', NULL, 'batch', 'source_product', NULL,
   'source_product_id', 'quality_grade', 30, 1,
   'automation/sourcing/grade_quality.py', '30 5 * * *',
   '派生作业：不采新数据，全表重算 quality_grade。5 处 Java 读路径拿它当筛选/排序(SalesRankingMapper 直接 IN(A,B))，静默跑挂=榜单与看板一起失真而无处可见'),
  -- 契约预留：pdd 起店后才由 Python 写 ingest_batch，此前 measure=batch 查不到批次属正常，monitor 保持 0
  ('order', '平台订单', NULL, 'batch', 'order_info', NULL,
   'shop_id,platform_order_sn', 'platform_order_sn,pay_amount', 24, 0,
   NULL, NULL,
   '抖音订单目前由 crawl_douyin_orders.py 手工触发，无常驻调度；拼多多起店后按批次契约接入'),
  ('after_sale', '平台售后', NULL, 'batch', 'refund_import_order', NULL,
   'shop_id,after_sales_id', 'after_sales_id', 24, 0, NULL, NULL, NULL),
  ('item', '平台在售商品', NULL, 'batch', 'platform_product', NULL,
   'shop_id,goods_id', 'goods_id,title', 48, 0, NULL, NULL,
   'platform_product 同时被后台编辑写入，update_time 不能当采集心跳'),
  ('item_daily', '平台商品日效果', NULL, 'batch', 'platform_item_daily', NULL,
   'shop_id,goods_id,stat_date', 'goods_id,stat_date', 30, 0, NULL, NULL,
   '目标表尚未建，P1 随拼多多采集一起落表'),
  ('promo_cost', '推广花费', NULL, 'batch', 'promo_cost_daily', NULL,
   'shop_id,campaign_id,stat_date', 'campaign_id,stat_date', 30, 0, NULL, NULL,
   '目标表尚未建，P1 随拼多多采集一起落表');
