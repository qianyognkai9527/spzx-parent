-- 货源订单管理功能增强：增加平台商品/货源商品关联及价格运费字段
-- 执行前请确认 order_source_relation 表已存在

ALTER TABLE `order_source_relation`
    ADD COLUMN `platform_product_id` BIGINT NULL COMMENT '平台商品ID' AFTER `platform_type`,
    ADD COLUMN `platform_product_code` VARCHAR(100) NULL COMMENT '平台商品编号' AFTER `platform_product_id`,
    ADD COLUMN `platform_product_title` VARCHAR(255) NULL COMMENT '平台商品标题' AFTER `platform_product_code`,
    ADD COLUMN `platform_selling_price` DECIMAL(10,2) NULL COMMENT '平台售价（定价）' AFTER `platform_product_title`,
    ADD COLUMN `platform_freight` DECIMAL(10,2) NULL COMMENT '平台运费' AFTER `platform_selling_price`,
    ADD COLUMN `source_product_id` BIGINT NULL COMMENT '货源商品ID' AFTER `platform_freight`,
    ADD COLUMN `source_product_code` VARCHAR(100) NULL COMMENT '货源商品编号' AFTER `source_product_id`,
    ADD COLUMN `source_product_title` VARCHAR(255) NULL COMMENT '货源商品标题' AFTER `source_product_code`,
    ADD COLUMN `source_selling_price` DECIMAL(10,2) NULL COMMENT '货源售价（进货价）' AFTER `source_product_title`,
    ADD COLUMN `source_freight` DECIMAL(10,2) NULL COMMENT '货源运费' AFTER `source_selling_price`,
    ADD COLUMN `order_status` INT NULL COMMENT '订单状态：1-待发货, 2-已发货, 3-已完成, 4-已取消' AFTER `source_freight`,
    ADD COLUMN `order_time` DATETIME NULL COMMENT '下单时间' AFTER `order_status`;

-- 建议添加索引以提升查询性能
ALTER TABLE `order_source_relation`
    ADD INDEX `idx_platform_product_id` (`platform_product_id`),
    ADD INDEX `idx_source_product_id` (`source_product_id`),
    ADD INDEX `idx_order_status` (`order_status`),
    ADD INDEX `idx_order_time` (`order_time`);
