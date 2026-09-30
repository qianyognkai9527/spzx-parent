-- platform_product 审计列类型收敛：varchar(64) → BIGINT
--
-- 起因（浏览器实测复现）：平台商品列表切到任一平台时 500，日志为
--   ResultMapException: Error attempting to get column 'create_by' from result set
--   Cause: NumberFormatException: For input string: "vgtest"
-- 实体 MallProduct.java:45,53 把 createBy/updateBy 声明为 Long（与全站其它表一致），
-- 而 platform_product 的两列是 varchar(64)。MyBatis-Plus 显式列出这些列，
-- 只要有一行存了非数字（视频生成联调时留下的测试商品 4722 create_by='vgtest'），
-- 整张表的 selectPage/selectList 全部报错，页面显示"您的网络有问题请稍后重试"。
--
-- 做法：非数字先置 NULL（不删任何业务行，测试商品与其 25 条视频任务记录都保留，
-- 由使用方在页面上自行删除），再把两列收敛成 BIGINT，与实体和其它表对齐。
-- 执行：mysql --defaults-extra-file=<cnf> --default-character-set=utf8mb4 -D db_spzx < platform_product_audit_columns_fix.sql
-- 重复执行安全（MODIFY 幂等；UPDATE 命中 0 行）。

SELECT COUNT(*) AS non_numeric_create_by_before_fix
  FROM platform_product WHERE create_by IS NOT NULL AND create_by NOT REGEXP '^[0-9]+$';

UPDATE platform_product SET create_by = NULL
 WHERE create_by IS NOT NULL AND create_by NOT REGEXP '^[0-9]+$';

UPDATE platform_product SET update_by = NULL
 WHERE update_by IS NOT NULL AND update_by NOT REGEXP '^[0-9]+$';

ALTER TABLE platform_product MODIFY COLUMN create_by BIGINT NULL COMMENT '创建人id';
ALTER TABLE platform_product MODIFY COLUMN update_by BIGINT NULL COMMENT '更新人id';

-- 校验：应与执行前的 SELECT COUNT(*) 前的总行数一致，且 0 行受影响
-- SELECT COUNT(*) FROM platform_product;
