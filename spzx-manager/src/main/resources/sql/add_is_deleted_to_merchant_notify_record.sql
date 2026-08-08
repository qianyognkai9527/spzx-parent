-- ===================================================
-- 修复继承 BaseEntity 但表缺失 is_deleted 列的问题
-- BaseEntity 定义: id, create_time, update_time, is_deleted
-- 以下表对应实体 extends BaseEntity，但建表时遗漏了该列
-- ===================================================

-- 1. 商户回调通知记录表
ALTER TABLE merchant_notify_record
    ADD COLUMN is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除 0-未删除 1-已删除'
    AFTER response_content;

-- 2. 付款信息表
ALTER TABLE payment_info
    ADD COLUMN is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '是否删除 0-未删除 1-已删除'
    AFTER update_time;
