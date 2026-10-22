-- order_item 增加权威 item_id 列(淘宝商品id)。
-- 来源: tradeSnap.htm 内嵌 JSON 的 itemSnapDO.itemId(每单权威, 见 collect_order_item_ids.py)。
-- 用途: 商品级退款绩效表的分母按 item_id 归集, 取代不可靠的「标题→item_id」映射。
-- 幂等: 列已存在时 MySQL 会报 1060, 属正常(本仓库无迁移框架, 手工执行)。
ALTER TABLE order_item
  ADD COLUMN item_id VARCHAR(64) DEFAULT NULL COMMENT '淘宝商品id(权威, 来自itemSnapDO)' AFTER product_title;
