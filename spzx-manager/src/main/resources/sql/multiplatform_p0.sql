-- 多平台可扩展架构 P0：建表与加列（DDL）
-- 依据 docs/superpowers/specs/2026-09-29-multiplatform-ingest-design.md
-- 只做加法：建表、加列、加索引。不删除/替换任何现有索引。
--
-- 执行顺序与字符集（本机 character_set_client 默认是 latin1，不设 utf8mb4 会把中文双重编码）：
--   mysql --default-character-set=utf8mb4 -D db_spzx < multiplatform_p0.sql        -- 建表/加列
--   mysql --default-character-set=utf8mb4 -D db_spzx < multiplatform_p0_seed.sql   -- 种子数据 + shop_id 回填
--   mysql  --default-character-set=utf8mb4 -D db_spzx < multiplatform_p0_verify.sql -- 前后对账
-- ALTER/CREATE INDEX 不可重复执行，重复运行请先确认列与索引是否已存在。

CREATE TABLE IF NOT EXISTS platform (
  code          TINYINT      NOT NULL COMMENT '平台码，沿用历史值 1=淘宝 2=抖音；3=拼多多',
  slug          VARCHAR(32)  NOT NULL COMMENT '英文标识，Python 目录/前端 key/枚举名',
  name          VARCHAR(32)  NOT NULL COMMENT '展示名，前端字典唯一来源',
  theme_color   CHAR(7)      NOT NULL COMMENT '看板/标签颜色',
  money_channel VARCHAR(32)  NOT NULL DEFAULT 'platform_settlement' COMMENT 'alipay|platform_settlement',
  enabled       TINYINT      NOT NULL DEFAULT 1 COMMENT '0=已登记未启用',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (code),
  UNIQUE KEY uk_platform_slug (slug)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '平台注册表';

CREATE TABLE IF NOT EXISTS shop (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  platform_code  TINYINT      NOT NULL,
  shop_name      VARCHAR(64)  NOT NULL,
  outer_shop_id  VARCHAR(64)  NULL COMMENT '平台侧店铺ID，未取到则留空',
  ingest_channel VARCHAR(16)  NOT NULL DEFAULT 'browser' COMMENT 'api|browser|export',
  credential_ref VARCHAR(128) NULL COMMENT '凭据引用：local 配置 key 或 chrome profile 目录名。严禁存明文密钥',
  cdp_port       INT          NULL COMMENT '浏览器通道使用的 CDP 端口',
  is_default     TINYINT      NOT NULL DEFAULT 0 COMMENT '1=该平台的历史默认店',
  status         TINYINT      NOT NULL DEFAULT 1 COMMENT '0=停用 1=启用',
  first_online_at DATE        NULL,
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_shop_platform_name (platform_code, shop_name),
  KEY idx_shop_platform (platform_code, is_default)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '店铺表（id 由种子脚本显式指定，保证回填值稳定）';

CREATE TABLE IF NOT EXISTS platform_capability (
  platform_code TINYINT      NOT NULL,
  capability    VARCHAR(32)  NOT NULL COMMENT 'ingest_order/ingest_after_sale/ingest_item/ingest_item_daily/ingest_promo_cost/publish_product/attach_media',
  supported     TINYINT      NOT NULL DEFAULT 0,
  channel       VARCHAR(16)  NULL COMMENT '该能力实际走的通道',
  note          VARCHAR(255) NULL,
  PRIMARY KEY (platform_code, capability)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '平台能力矩阵，前端入口显隐依据';

-- ============ 店级事实表加 shop_id ============

ALTER TABLE platform_product        ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_type;
ALTER TABLE order_info              ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_type;
ALTER TABLE refund_import_order     ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_type;
ALTER TABLE refund_analysis_report  ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_type;
ALTER TABLE refund_analysis_detail  ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_type;
ALTER TABLE sync_alert              ADD COLUMN shop_id BIGINT NULL COMMENT '所属店铺' AFTER platform_sku_id;

CREATE INDEX idx_platform_product_shop ON platform_product (shop_id);
CREATE INDEX idx_order_info_shop       ON order_info (shop_id);
CREATE INDEX idx_refund_import_shop    ON refund_import_order (shop_id);
CREATE INDEX idx_refund_report_shop    ON refund_analysis_report (shop_id);
CREATE INDEX idx_refund_detail_shop    ON refund_analysis_detail (shop_id);
CREATE INDEX idx_sync_alert_shop       ON sync_alert (shop_id);
