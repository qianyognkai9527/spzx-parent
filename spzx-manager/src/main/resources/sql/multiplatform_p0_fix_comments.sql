-- 多平台 P0 收尾：修复列/表注释的双重编码
--
-- 起因：本机 mysql 客户端默认 character_set_client=latin1，multiplatform_p0.sql 的
-- CREATE TABLE / ALTER TABLE 首次执行时没带 --default-character-set=utf8mb4，
-- 中文注释被按 latin1 解释后再次编码，库里存成「æ‰€å±žåº—é“º」这类乱码。
-- 影响面只有注释（元数据），行数据与列字符集已核实为 utf8mb4 正常：
--   SELECT HEX(LEFT(name,1)) FROM platform;  -- E6B798 = 淘，正确
-- 所以这里只重写注释，不动类型/默认值/顺序；MODIFY 语句按 SHOW CREATE TABLE 原样重述定义。
--
-- 必须带 utf8mb4 执行，否则再花一次：
--   mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < multiplatform_p0_fix_comments.sql
-- 本脚本可重复执行。

ALTER TABLE platform MODIFY COLUMN code        TINYINT      NOT NULL COMMENT '平台码，沿用历史值 1=淘宝 2=抖音；3=拼多多';
ALTER TABLE platform MODIFY COLUMN slug        VARCHAR(32)  NOT NULL COMMENT '英文标识，Python 目录/前端 key/枚举名';
ALTER TABLE platform MODIFY COLUMN name        VARCHAR(32)  NOT NULL COMMENT '展示名，前端字典唯一来源';
ALTER TABLE platform MODIFY COLUMN theme_color CHAR(7)      NOT NULL COMMENT '看板/标签颜色';
ALTER TABLE platform MODIFY COLUMN enabled     TINYINT      NOT NULL DEFAULT 1 COMMENT '0=已登记未启用';
ALTER TABLE platform COMMENT = '平台注册表';

ALTER TABLE shop MODIFY COLUMN outer_shop_id  VARCHAR(64)  NULL COMMENT '平台侧店铺ID，未取到则留空';
ALTER TABLE shop MODIFY COLUMN credential_ref VARCHAR(128) NULL COMMENT '凭据引用：local 配置 key 或 chrome profile 目录名。严禁存明文密钥';
ALTER TABLE shop MODIFY COLUMN cdp_port       INT          NULL COMMENT '浏览器通道使用的 CDP 端口';
ALTER TABLE shop MODIFY COLUMN is_default     TINYINT      NOT NULL DEFAULT 0 COMMENT '1=该平台的历史默认店';
ALTER TABLE shop MODIFY COLUMN status         TINYINT      NOT NULL DEFAULT 1 COMMENT '0=停用 1=启用';
ALTER TABLE shop COMMENT = '店铺表（id 由种子脚本显式指定，保证回填值稳定）';

ALTER TABLE platform_capability MODIFY COLUMN channel VARCHAR(16) NULL COMMENT '该能力实际走的通道';
ALTER TABLE platform_capability COMMENT = '平台能力矩阵，前端入口显隐依据';

ALTER TABLE platform_product       MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';
ALTER TABLE order_info             MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';
ALTER TABLE refund_import_order    MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';
ALTER TABLE refund_analysis_report MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';
ALTER TABLE refund_analysis_detail MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';
ALTER TABLE sync_alert             MODIFY COLUMN shop_id BIGINT NULL COMMENT '所属店铺';

-- 校验：下列查询应返回 0 行（存在 C3 开头字节即仍是双重编码）
-- SELECT TABLE_NAME, COLUMN_NAME, COLUMN_COMMENT FROM information_schema.COLUMNS
--  WHERE TABLE_SCHEMA='db_spzx' AND COLUMN_NAME='shop_id' AND HEX(COLUMN_COMMENT) LIKE 'C3%';
