-- ============================================================
-- 表名重命名：见名知义
-- 将所有 mall_ 前缀的表名改为更直观的名称
-- ============================================================

-- 刷单人员/买家秀人员管理
RENAME TABLE `mall_oper` TO `brush_person`;

-- 刷单订单（记录佣金返还等）
RENAME TABLE `mall_add_order` TO `brush_order`;

-- 刷单评价订单（含评价状态、评语等）
RENAME TABLE `mall_farm_order` TO `brush_eval_order`;

-- 刷单订单与媒体资源关联
RENAME TABLE `mall_order_resource` TO `brush_order_resource`;

-- 平台商品基本信息
RENAME TABLE `mall_product` TO `platform_product`;

-- 平台商品历史标题
RENAME TABLE `mall_product_title` TO `platform_product_title`;

-- 平台商品SKU
RENAME TABLE `mall_product_sku` TO `platform_product_sku`;

-- 平台商品与货源关联
RENAME TABLE `mall_product_link` TO `product_source_link`;

-- 货源工厂信息
RENAME TABLE `mall_product_factory` TO `product_factory`;

-- 商品图片视频资源
RENAME TABLE `mall_product_picvideo` TO `product_media`;

-- 退款分析报表
RENAME TABLE `mall_refund_record` TO `refund_analysis_report`;

-- 退款分析报表详情
RENAME TABLE `mall_refund_record_detail` TO `refund_analysis_detail`;

-- 退款导入订单数据
RENAME TABLE `mall_refund_order` TO `refund_import_order`;
