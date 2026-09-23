-- 2026-09-23 性能/正确性索引补丁
-- 状态：已于本地 db_spzx 执行核实（kw_title_suggestion / brush_order / order_statistics 已生效）
-- 前提：db_optimization_plan.sql 已落地
-- 说明：实库索引现状与仓库历史 DDL 有出入，重跑前以 SHOW INDEX 为准

-- 1. kw_title_suggestion：按 task_id 查询（KwTaskService.detail/pickTitles）无索引
ALTER TABLE kw_title_suggestion ADD INDEX idx_task (task_id);

-- 2. brush_order：EvalGapMapper 关联 bo.product_id = CONCAT('', pp.id) 无索引，每行触发全表扫
ALTER TABLE brush_order ADD INDEX idx_product_id (product_id);

-- 3. order_source_relation：[实库核实] idx_order_no 与 uk_platform_order_source
--    已建在 order_no/source_order_no 上（仓库 add_platform_type.sql 的 order_id 版本已过时），
--    查询列已有索引，本条无需执行，保留仅作参考：
-- ALTER TABLE order_source_relation ADD INDEX idx_order_no (order_no);

-- 4. order_statistics：任务重跑防双份统计。
--    [实库核实] 按 (platform_type, order_date) 分组无重复行，去重 DELETE 无需执行；
--    配合 OrderStatisticsTask 已改为"先删后插"幂等写入，转唯一键已完成。
-- DELETE s1 FROM order_statistics s1
--     JOIN order_statistics s2
--       ON s1.platform_type = s2.platform_type
--      AND s1.order_date <=> s2.order_date
--      AND s1.id > s2.id;
ALTER TABLE order_statistics DROP INDEX idx_platform_date;
ALTER TABLE order_statistics ADD UNIQUE KEY uk_platform_date (platform_type, order_date);

-- ============================================================
-- 已知遗留（本轮未改，需要表结构方案评审后再做）：
-- a) is_deleted 参与唯一键的表（brand/category/order_source_relation 的 uk）：
--    同一业务键"删除→重建→再删除"会撞唯一键。方案：唯一键中的 is_deleted
--    改为 deleted_at DATETIME NULL（0/1 → NULL/时间戳），涉及 @TableLogic 语义调整。
-- b) source_product_sales_history / inventory_change_log / product_media_variant
--    三表被查询引用但仓库内无 DDL（外部爬虫建表），建议补录：
--    至少确认 (source_product_id, snapshot_time/create_time) 复合索引存在。
-- ============================================================
