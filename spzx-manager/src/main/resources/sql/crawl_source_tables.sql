-- ============================================================
-- 爬虫货源数据落库:扩展 source_product + 新建 source_factory
-- 执行库:db_spzx
-- ============================================================

-- A. 扩展 source_product 表(加爬虫特有列)
ALTER TABLE source_product
  ADD COLUMN supplier_name      VARCHAR(100) DEFAULT NULL COMMENT '供应商名称(爬虫)' AFTER eval_with_image_count,
  ADD COLUMN repurchase_rate    DECIMAL(5,1) DEFAULT NULL COMMENT '回头率%(爬虫)' AFTER supplier_name,
  ADD COLUMN sales_count        INT          DEFAULT NULL COMMENT '全网销量(爬虫)' AFTER repurchase_rate,
  ADD COLUMN category_name      VARCHAR(50)  DEFAULT NULL COMMENT '类目(爬虫)' AFTER sales_count,
  ADD COLUMN keyword            VARCHAR(50)  DEFAULT NULL COMMENT '关键词(爬虫)' AFTER category_name,
  ADD COLUMN trust_years        INT          DEFAULT NULL COMMENT '诚信通年限(爬虫)' AFTER keyword,
  ADD COLUMN source_factory_id  BIGINT       DEFAULT NULL COMMENT '关联source_factory(爬虫厂家)' AFTER trust_years,
  ADD COLUMN crawl_time         DATETIME     DEFAULT NULL COMMENT '采集时间' AFTER source_factory_id;

ALTER TABLE source_product
  ADD INDEX idx_offer_code (source_product_code),
  ADD INDEX idx_category (category_name),
  ADD INDEX idx_source_factory (source_factory_id);

-- B. 新建 source_factory 表(工厂排行榜)
CREATE TABLE IF NOT EXISTS source_factory (
  id                   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  factory_name         VARCHAR(100) NOT NULL COMMENT '厂家名称',
  trust_years          INT          DEFAULT NULL COMMENT '诚信通年限',
  product_count        INT          DEFAULT 0 COMMENT '商品数',
  avg_repurchase_rate  DECIMAL(5,1) DEFAULT NULL COMMENT '平均回头率%',
  total_sales          INT          DEFAULT 0 COMMENT '总销量',
  category_name        VARCHAR(50)  DEFAULT NULL COMMENT '主类目',
  factory_url          VARCHAR(500) DEFAULT NULL COMMENT '厂家链接(1688店铺)',
  rep_offer_id         VARCHAR(50)  DEFAULT NULL COMMENT '代表商品ID',
  rep_product_url      VARCHAR(500) DEFAULT NULL COMMENT '代表商品链接',
  platform_type        TINYINT      NOT NULL DEFAULT 1 COMMENT '1淘宝2抖音',
  create_time          DATETIME     NOT NULL COMMENT '创建时间',
  update_time          DATETIME     DEFAULT NULL COMMENT '更新时间',
  is_deleted           INT          NOT NULL DEFAULT 0 COMMENT '逻辑删除',
  PRIMARY KEY (id),
  INDEX idx_factory_name (factory_name),
  INDEX idx_repurchase (avg_repurchase_rate),
  INDEX idx_trust_years (trust_years),
  INDEX idx_product_count (product_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫工厂排行榜';

-- C. 菜单注册:工厂排行榜页面(后端动态菜单要求 component=路由name)
-- 先查"货源与商品"父菜单 id(product 父路由),若不存在用 38 兜底
INSERT INTO sys_menu (parent_id, title, component, sort_value, status, create_time, update_time)
SELECT COALESCE((SELECT id FROM (SELECT id FROM sys_menu WHERE component='product' LIMIT 1) t), 38),
       '工厂排行榜', 'sourceFactoryRank', 50, 1, NOW(), NOW();

-- 授权给 admin 角色(id=9,若不同请调整)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, id FROM sys_menu WHERE component='sourceFactoryRank';
