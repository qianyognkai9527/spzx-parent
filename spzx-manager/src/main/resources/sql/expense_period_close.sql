-- expense_period_close.sql : 对账月度关账（锁定后该月账单不可改/删/重复导入）
CREATE TABLE IF NOT EXISTS expense_period_close (
  period CHAR(7) NOT NULL PRIMARY KEY COMMENT '关账月份 yyyy-MM',
  closed_by BIGINT UNSIGNED DEFAULT NULL COMMENT '操作人',
  closed_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对账关账月份';
