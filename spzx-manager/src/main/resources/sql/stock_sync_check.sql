-- stock_sync_check.sql (2026-10-18) ISV 同步 0 库存行级核验（spec P4）。
CREATE TABLE IF NOT EXISTS stock_sync_check (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  check_time DATETIME NOT NULL,
  taobao_item_id BIGINT NOT NULL,
  offer_id BIGINT NULL,
  record_text TEXT NULL,
  verdict TINYINT NOT NULL COMMENT '1=成功同步为0 2=无同步记录 3=失败/异常',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_time (check_time),
  KEY idx_item (taobao_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ISV同步0库存行级核验';
