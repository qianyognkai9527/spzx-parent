-- 刷单功能优化SQL
-- 1. mall_oper: 添加platform_type (0=通用, 刷单人员不分平台)
ALTER TABLE mall_oper ADD COLUMN platform_type INT DEFAULT 0 COMMENT '平台类型：0-通用,1-淘宝,2-抖音';

-- 2. mall_add_order: 添加platform_type, hire_is_pay, seed_is_pay, settlement_time
ALTER TABLE mall_add_order ADD COLUMN platform_type INT DEFAULT 1 COMMENT '平台类型：1-淘宝,2-抖音';
ALTER TABLE mall_add_order ADD COLUMN hire_is_pay INT DEFAULT 0 COMMENT '佣金是否已返：0-未返,1-已返';
ALTER TABLE mall_add_order ADD COLUMN seed_is_pay INT DEFAULT 0 COMMENT '本金是否已返：0-未返,1-已返';
ALTER TABLE mall_add_order ADD COLUMN settlement_time DATETIME NULL COMMENT '返佣时间';

-- 3. mall_farm_order: 添加platform_type
ALTER TABLE mall_farm_order ADD COLUMN platform_type INT DEFAULT 1 COMMENT '平台类型：1-淘宝,2-抖音';
