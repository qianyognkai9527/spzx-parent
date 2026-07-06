-- ============================================
-- 创建 mall_product_factory 工厂基本信息表
-- 该表之前缺失，导致 MallProductFactoryController 和 ProductMapper.xml 中的接口报错
-- @since 2025-08-20
-- ============================================

CREATE TABLE IF NOT EXISTS `mall_product_factory` (
  `id`            bigint        NOT NULL AUTO_INCREMENT COMMENT '主键',
  `factory_name`  varchar(100)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '工厂名称',
  `url`           varchar(500)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '工厂链接地址',
  `create_by`     bigint        DEFAULT NULL COMMENT '创建人',
  `create_time`   datetime      NOT NULL COMMENT '创建时间',
  `update_by`     bigint        DEFAULT NULL COMMENT '更新人',
  `update_time`   datetime      DEFAULT NULL COMMENT '更新时间',
  `remark`        varchar(255)  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  `deploy_count`  int           DEFAULT 0 COMMENT '铺货商品数',
  `platform_type` tinyint UNSIGNED NOT NULL DEFAULT 1 COMMENT '平台类型：1-淘宝, 2-抖音',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_platform_create` (`platform_type`, `create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC COMMENT='工厂基本信息表';
