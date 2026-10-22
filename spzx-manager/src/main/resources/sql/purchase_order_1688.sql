-- 1688 买家采购订单（全历史, 来源 mtop.1688.trading.dataline.service / OrderListDataLineService.buyerOrderList）。
-- 用途: 每个有效订单的 1688 采购成本 → 真实盈亏。
-- 金额单位统一存「元」(接口原始值是分, 采集器 /100)。
CREATE TABLE IF NOT EXISTS purchase_order_1688 (
  id BIGINT NOT NULL AUTO_INCREMENT,
  order_no VARCHAR(32) NOT NULL COMMENT '1688订单号',
  gmt_create DATETIME DEFAULT NULL COMMENT '下单时间',
  gmt_payment DATETIME DEFAULT NULL COMMENT '付款时间',
  sum_payment DECIMAL(12,2) DEFAULT NULL COMMENT '实付总额(元,含运费)',
  sum_product_payment DECIMAL(12,2) DEFAULT NULL COMMENT '商品总额(元)',
  carriage DECIMAL(10,2) DEFAULT NULL COMMENT '运费(元)',
  status VARCHAR(32) DEFAULT NULL,
  status_label VARCHAR(32) DEFAULT NULL,
  seller_login_id VARCHAR(64) DEFAULT NULL COMMENT '卖家loginId',
  entries_json MEDIUMTEXT COMMENT '商品明细[{sourceId,productName,quantity,amount,unitPrice,specInfo}]',
  raw_json MEDIUMTEXT,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_po1688_order (order_no),
  KEY idx_po1688_create (gmt_create)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
