-- ============================================================
-- ClickHouse 初始化脚本
-- 执行: docker exec -i clickhouse clickhouse-client -u spzx --password spzx123 < this_file.sql
-- ============================================================

-- 订单统计表（接收 Canal → Flink 同步的数据）
CREATE TABLE IF NOT EXISTS spzx_analytics.order_statistics (
    id Int64,
    platform_type Int32,
    order_date Date,
    total_amount Decimal(18,2),
    total_num Int64,
    total_count Int64,
    create_time DateTime,
    update_time DateTime,
    is_deleted Int32 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (platform_type, order_date)
PARTITION BY toYYYYMM(order_date)
SETTINGS index_granularity = 8192;

-- 操作日志表（接收 Canal → Flink 同步的数据）
CREATE TABLE IF NOT EXISTS spzx_analytics.sys_oper_log (
    id Int64,
    title String,
    method String,
    request_method String,
    operator_type String,
    oper_name String,
    oper_url String,
    oper_ip String,
    oper_param String,
    json_result String,
    status Int32,
    error_msg String,
    create_time DateTime,
    update_time DateTime,
    is_deleted Int32 DEFAULT 0
) ENGINE = MergeTree()
ORDER BY (create_time)
PARTITION BY toYYYYMM(create_time)
SETTINGS index_granularity = 8192;