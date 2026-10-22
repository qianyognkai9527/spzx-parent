-- onsale_snapshot: 铺货平台「销售中」商品每日快照 (sync_onsale.py, spec 2026-10-19 onsale-refactor §3.1)
CREATE TABLE IF NOT EXISTS onsale_snapshot (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  taobao_item_id BIGINT NOT NULL,
  source_product_id BIGINT NULL,
  shop_status VARCHAR(20) NOT NULL DEFAULT '',
  source_status VARCHAR(20) NOT NULL DEFAULT '',
  source_price DECIMAL(10,2) NULL,
  source_stock INT NULL,
  raw VARCHAR(1024) NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_item (snapshot_date, taobao_item_id),
  KEY idx_date (snapshot_date),
  KEY idx_spi (source_product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='铺货平台在售商品每日快照';
