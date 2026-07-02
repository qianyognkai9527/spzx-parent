-- ============================================
-- 商品域：添加 platform_type 并优化索引
-- ============================================

-- 1. brand 品牌表
ALTER TABLE `brand` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `brand`
    ADD INDEX `idx_platform_del_create` (`platform_type`, `is_deleted`, `create_time`),
    ADD UNIQUE INDEX `uk_platform_name` (`platform_type`, `name`, `is_deleted`);

-- 2. category 分类表
ALTER TABLE `category` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `category`
    ADD INDEX `idx_platform_parent` (`platform_type`, `parent_id`),
    ADD UNIQUE INDEX `uk_platform_name_parent` (`platform_type`, `name`, `parent_id`, `is_deleted`);

-- 3. category_brand 分类品牌关联表
ALTER TABLE `category_brand` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `category_brand`
    ADD INDEX `idx_platform_del` (`platform_type`, `is_deleted`),
    ADD INDEX `idx_platform_category` (`platform_type`, `category_id`, `is_deleted`),
    ADD INDEX `idx_platform_brand` (`platform_type`, `brand_id`, `is_deleted`);

-- 4. product 商品表
ALTER TABLE `product` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `product`
    ADD INDEX `idx_platform_del_create` (`platform_type`, `is_deleted`, `create_time`),
    ADD INDEX `idx_platform_factory` (`platform_type`, `product_factory_id`),
    ADD INDEX `idx_platform_source_code` (`platform_type`, `source_product_code`);

-- 5. product_sku 商品SKU表
ALTER TABLE `product_sku` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `product_sku`
    ADD INDEX `idx_platform_product_del` (`platform_type`, `product_id`, `is_deleted`),
    ADD INDEX `idx_platform_sku_code` (`platform_type`, `sku_code`);

-- 6. product_spec 商品规格表
ALTER TABLE `product_spec` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `product_spec`
    ADD INDEX `idx_platform_del_create` (`platform_type`, `is_deleted`, `create_time`);

-- 7. product_details 商品详情表
ALTER TABLE `product_details` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `product_details`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`);

-- 8. product_bind_relation 商品绑定关系表
ALTER TABLE `product_bind_relation` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `product_bind_relation`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`);

-- ============================================
-- 订单域：添加 platform_type 并优化索引
-- ============================================

-- 9. order_info 订单表
ALTER TABLE `order_info` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `order_info`
    ADD INDEX `idx_platform_del_create` (`platform_type`, `is_deleted`, `create_time`),
    ADD INDEX `idx_platform_order_no` (`platform_type`, `order_no`),
    ADD INDEX `idx_platform_user` (`platform_type`, `user_id`),
    ADD INDEX `idx_platform_status` (`platform_type`, `order_status`);

-- 10. order_item 订单项表
ALTER TABLE `order_item` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `order_item`
    ADD INDEX `idx_platform_order` (`platform_type`, `order_id`);

-- 11. order_log 订单日志表
ALTER TABLE `order_log` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `order_log`
    ADD INDEX `idx_platform_order` (`platform_type`, `order_id`);

-- 12. order_statistics 订单统计表
ALTER TABLE `order_statistics` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `order_statistics`
    ADD INDEX `idx_platform_date` (`platform_type`, `order_date`);

-- ============================================
-- 运营域：添加 platform_type 并优化索引
-- ============================================

-- 13. mall_product 运营商品表
ALTER TABLE `mall_product` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product`
    ADD INDEX `idx_platform_create` (`platform_type`, `create_time`);

-- 14. mall_product_sku 运营商品SKU表
ALTER TABLE `mall_product_sku` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product_sku`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`);

-- 15. mall_product_title 运营商品标题表
ALTER TABLE `mall_product_title` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product_title`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`);

-- 16. mall_product_link 运营商品链接表
ALTER TABLE `mall_product_link` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product_link`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`);

-- 17. mall_product_factory 工厂表
ALTER TABLE `mall_product_factory` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product_factory`
    ADD INDEX `idx_platform_create` (`platform_type`, `create_time`);

-- 18. mall_oper 刷手/买手秀表
ALTER TABLE `mall_oper` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_oper`
    ADD INDEX `idx_platform_type_create` (`platform_type`, `type`, `create_time`);

-- 19. mall_add_order 补单表
ALTER TABLE `mall_add_order` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_add_order`
    ADD INDEX `idx_platform_order_time` (`platform_type`, `order_time`),
    ADD INDEX `idx_platform_brush` (`platform_type`, `brush_person_id`);

-- 20. mall_farm_order 农场订单表
ALTER TABLE `mall_farm_order` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_farm_order`
    ADD INDEX `idx_platform_create` (`platform_type`, `create_time`),
    ADD INDEX `idx_platform_shoot` (`platform_type`, `shoot_person_id`);

-- 21. mall_order_resource 订单资源表
ALTER TABLE `mall_order_resource` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音';

-- 22. mall_refund_order 退款订单表
ALTER TABLE `mall_refund_order` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音';

-- 23. mall_refund_record 退款记录表
ALTER TABLE `mall_refund_record` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_refund_record`
    ADD INDEX `idx_platform_create` (`platform_type`, `create_time`);

-- 24. mall_refund_record_detail 退款记录详情表
ALTER TABLE `mall_refund_record_detail` 
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音';

-- ============================================
-- 订单域补充：添加 platform_type 并优化索引
-- ============================================

-- 25. order_source_relation 订单货源关联表
ALTER TABLE `order_source_relation`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `order_source_relation`
    ADD INDEX `idx_platform_order` (`platform_type`, `order_id`),
    ADD INDEX `idx_platform_source_order` (`platform_type`, `source_order_id`),
    ADD UNIQUE INDEX `uk_platform_order_source` (`platform_type`, `order_id`, `source_order_id`, `is_deleted`);

-- ============================================
-- 运营域补充：添加 platform_type 并优化索引
-- ============================================

-- 26. mall_product_picvideo 商品图片视频表
ALTER TABLE `mall_product_picvideo`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `mall_product_picvideo`
    ADD INDEX `idx_platform_product` (`platform_type`, `product_id`),
    ADD INDEX `idx_platform_person` (`platform_type`, `person_id`);

-- ============================================
-- 用户域：添加 platform_type 并优化索引
-- ============================================

-- 27. user_collect 用户收藏表
ALTER TABLE `user_collect`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `user_collect`
    ADD INDEX `idx_platform_user_del` (`platform_type`, `user_id`, `is_deleted`),
    ADD INDEX `idx_platform_sku` (`platform_type`, `sku_id`);

-- 28. user_browse_history 用户浏览记录表
ALTER TABLE `user_browse_history`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `user_browse_history`
    ADD INDEX `idx_platform_user_del` (`platform_type`, `user_id`, `is_deleted`),
    ADD INDEX `idx_platform_sku` (`platform_type`, `sku_id`);

-- 29. user_cost 用户收支表
ALTER TABLE `user_cost`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `remark`;
ALTER TABLE `user_cost`
    ADD INDEX `idx_platform_user_del` (`platform_type`, `user_id`, `is_deleted`),
    ADD INDEX `idx_platform_pay_time` (`platform_type`, `pay_time`);

-- ============================================
-- 优惠券域：添加 platform_type 并优化索引
-- ============================================

-- 30. coupon_info 优惠券信息表
ALTER TABLE `coupon_info`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `coupon_info`
    ADD INDEX `idx_platform_del_create` (`platform_type`, `is_deleted`, `create_time`),
    ADD INDEX `idx_platform_status` (`platform_type`, `publish_status`);

-- 31. coupon_user 优惠券领用表
ALTER TABLE `coupon_user`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `coupon_user`
    ADD INDEX `idx_platform_user` (`platform_type`, `user_id`),
    ADD INDEX `idx_platform_coupon` (`platform_type`, `coupon_id`),
    ADD INDEX `idx_platform_order` (`platform_type`, `order_id`);

-- 32. coupon_range 优惠券范围表
ALTER TABLE `coupon_range`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `coupon_range`
    ADD INDEX `idx_platform_coupon` (`platform_type`, `coupon_id`),
    ADD INDEX `idx_platform_range` (`platform_type`, `range_id`, `range_type`);

-- ============================================
-- 支付域：添加 platform_type 并优化索引
-- ============================================

-- 33. payment_info 支付信息表
ALTER TABLE `payment_info`
    ADD COLUMN `platform_type` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音' AFTER `is_deleted`;
ALTER TABLE `payment_info`
    ADD INDEX `idx_platform_order_no` (`platform_type`, `order_no`),
    ADD INDEX `idx_platform_user` (`platform_type`, `user_id`),
    ADD INDEX `idx_platform_trade_no` (`platform_type`, `out_trade_no`);
