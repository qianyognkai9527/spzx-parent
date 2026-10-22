-- 低库存规格页的人工处理标记（2026-10-17）。
-- 页面本身不改库存/不动淘宝——这里的行只是「人按数据做完下架/删除/下架SKU 后的留痕」，防时间久遗忘。
-- 一行一个货源（source_product.id 主键）；重复标记原地覆盖（UPSERT），撤销即删行。
CREATE TABLE IF NOT EXISTS low_stock_handle (
  source_product_id BIGINT PRIMARY KEY COMMENT 'source_product.id（低库存页一行一个货源）',
  handle_type TINYINT NOT NULL COMMENT '人工处理标记：1=已下架 2=已删除 3=已下架SKU',
  handle_by BIGINT NOT NULL COMMENT '标记人 sys_user.id',
  handle_time DATETIME NOT NULL COMMENT '标记时间',
  update_time DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
