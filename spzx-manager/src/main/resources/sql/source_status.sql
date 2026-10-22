-- source_status.sql (2026-10-18) 货源存活标记：库存监控闭环 P1 前置。
-- 1=正常 0=已失效(1688商品下架/打不开) NULL=未检测。写入方: backfill_offer_archive.py / detect_stock_change --tiered
ALTER TABLE source_product ADD COLUMN source_status TINYINT NULL COMMENT '货源存活:1=正常 0=已失效 NULL=未检测(2026-10-18库存监控)';
