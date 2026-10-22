-- 淘宝商品 ↔ 1688 货源映射。来源 automation/sourcing/sku_match_report.json
-- （import_offer_map.py 一次性导入；isv_sku_match.py 每轮结束 UPSERT 刷新）。
-- 一个淘宝商品只挂一个货源（uk_item）；一个货源对应多个淘宝商品是正常态。
CREATE TABLE IF NOT EXISTS taobao_offer_map (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  taobao_item_id BIGINT NOT NULL COMMENT '淘宝商品 itemId',
  offer_id BIGINT NOT NULL COMMENT '1688 货源 offerId',
  source_product_id BIGINT NULL COMMENT 'source_product.id，导入时解析 source_product_url 回填；解析不到留 NULL',
  update_time DATETIME NULL,
  UNIQUE KEY uk_item (taobao_item_id),
  KEY idx_offer (offer_id),
  KEY idx_sp (source_product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 菜单：运营管理(id=38) 下「低库存规格」，sort 22（推广计划 21 之后、AI选词 60 之前）
INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 79, 38, '低库存规格', 'lowStock', 22, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE id = 79);

-- 角色授权照推广日报（76/77/78 都是 role_id=9）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, 79 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_role_menu WHERE role_id = 9 AND menu_id = 79);
