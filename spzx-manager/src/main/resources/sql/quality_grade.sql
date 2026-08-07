-- task2: 优质等级 + 数据来源字段
-- source_product: 加 data_source(区分1688搜索候选 vs ISV已铺货, 因两者 platform_type 都=1) + quality_grade
-- source_factory: 加 quality_grade (厂家 platform_type 已能区分淘宝/抖音, 无需 data_source)
-- 注意: 仅首次执行; 列已存在会报错

ALTER TABLE source_product
  ADD COLUMN data_source tinyint NOT NULL DEFAULT 1 COMMENT '数据来源:1=1688搜索候选 2=ISV已铺货',
  ADD COLUMN quality_grade char(1) DEFAULT NULL COMMENT '优质等级:A/B/C NULL=未达标',
  ADD KEY idx_data_source (data_source),
  ADD KEY idx_quality_grade (quality_grade);

ALTER TABLE source_factory
  ADD COLUMN quality_grade char(1) DEFAULT NULL COMMENT '优质等级:A/B NULL=未达标',
  ADD KEY idx_quality_grade (quality_grade);

-- 回填 data_source: 抖音ISV行(platform_type=2) -> data_source=2; 搜索候选(platform_type=1) 默认1
UPDATE source_product SET data_source = 2 WHERE platform_type = 2;
