-- P0 迁移前后对账基线。执行 multiplatform_p0.sql 前后各跑一次，两侧输出必须一致。
SELECT 'platform_product_rows' k, COUNT(*) v, NULL s FROM platform_product
UNION ALL SELECT 'platform_product_code_sum', COUNT(DISTINCT code), NULL FROM platform_product
UNION ALL SELECT 'platform_product_pricing_sum', SUM(pricing IS NOT NULL), ROUND(SUM(COALESCE(pricing, 0)), 2) FROM platform_product
UNION ALL SELECT 'order_info_rows', COUNT(*), NULL FROM order_info
UNION ALL SELECT 'order_info_amount_sum', ROUND(SUM(COALESCE(total_amount, 0)), 2), NULL FROM order_info
UNION ALL SELECT 'refund_import_rows', COUNT(*), NULL FROM refund_import_order
UNION ALL SELECT 'refund_import_money_sum', ROUND(SUM(COALESCE(refund_money, 0)), 2), NULL FROM refund_import_order
UNION ALL SELECT 'refund_report_rows', COUNT(*), NULL FROM refund_analysis_report
UNION ALL SELECT 'refund_detail_rows', COUNT(*), NULL FROM refund_analysis_detail
UNION ALL SELECT 'sync_alert_rows', COUNT(*), NULL FROM sync_alert
UNION ALL SELECT 'sync_alert_unresolved', COUNT(*), NULL FROM sync_alert WHERE shop_id IS NULL
UNION ALL SELECT 'shop_rows', COUNT(*), NULL FROM shop
UNION ALL SELECT 'shop_default_rows', COUNT(*), NULL FROM shop WHERE is_default = 1;
