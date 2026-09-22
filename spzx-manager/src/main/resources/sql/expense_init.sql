-- 对账管理初始化（幂等可重复执行）2026-09-22
-- 设计文档: docs/superpowers/specs/2026-09-22-expense-tracking-design.md

CREATE TABLE IF NOT EXISTS expense_order (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  expense_date DATE NOT NULL COMMENT '消费日期（按日统计分组键）',
  txn_time DATETIME COMMENT '交易时间（导入=交易创建时间；手工可空）',
  amount DECIMAL(12,2) NOT NULL COMMENT '支出金额，正数',
  channel VARCHAR(32) NOT NULL DEFAULT '其他' COMMENT '渠道：支付宝/淘宝/京东/拼多多/抖音商城/美团/其他',
  source TINYINT NOT NULL COMMENT '来源：1支付宝导入 2手工录入',
  title VARCHAR(255) COMMENT '商品说明/内容',
  counterparty VARCHAR(128) COMMENT '交易分类（导入=支付宝交易分类，如餐饮美食/日用百货）',
  alipay_trade_no VARCHAR(128) DEFAULT NULL COMMENT '支付宝交易订单号（去重键，手工为NULL；实测最长75字符）',
  remark VARCHAR(255),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_trade_no (alipay_trade_no),
  KEY idx_expense_date (expense_date),
  KEY idx_channel (channel)
) COMMENT '消费账单记录';

CREATE TABLE IF NOT EXISTS expense_tag (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(32) NOT NULL COMMENT '标签名',
  color VARCHAR(16) COMMENT '前端标签色（el-tag type: primary/success/info/warning/danger）',
  sort_value INT DEFAULT 0,
  status TINYINT DEFAULT 1 COMMENT '1启用 0停用（停用不删，历史关联保留）',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name)
) COMMENT '消费标签';

CREATE TABLE IF NOT EXISTS expense_order_tag (
  order_id BIGINT NOT NULL,
  tag_id BIGINT NOT NULL,
  PRIMARY KEY (order_id, tag_id),
  KEY idx_tag_id (tag_id)
) COMMENT '账单-标签关联';

-- 预置标签（幂等）
INSERT INTO expense_tag (name, color, sort_value) SELECT '购物', 'primary', 1 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='购物');
INSERT INTO expense_tag (name, color, sort_value) SELECT '饮食', 'success', 2 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='饮食');
INSERT INTO expense_tag (name, color, sort_value) SELECT '交通', 'info', 3 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='交通');
INSERT INTO expense_tag (name, color, sort_value) SELECT '日用', 'warning', 4 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='日用');
INSERT INTO expense_tag (name, color, sort_value) SELECT '娱乐', 'danger', 5 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='娱乐');
INSERT INTO expense_tag (name, color, sort_value) SELECT '通讯', 'info', 6 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='通讯');
INSERT INTO expense_tag (name, color, sort_value) SELECT '医疗', 'danger', 7 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='医疗');
INSERT INTO expense_tag (name, color, sort_value) SELECT '其他', 'info', 8 WHERE NOT EXISTS (SELECT 1 FROM expense_tag WHERE name='其他');

-- 菜单：父「对账管理」+ 3 子页（component=前端路由 name，幂等）
INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 69, 0, '对账管理', 'expense', 5, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'expense');

INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 70, 69, '账单记录', 'expenseOrder', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'expenseOrder');

INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 71, 69, '标签管理', 'expenseTag', 2, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'expenseTag');

INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 72, 69, '统计说明', 'expenseStats', 3, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'expenseStats');

-- 授权 admin 角色(role 9)（幂等）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, m.id FROM sys_menu m
WHERE m.id IN (69, 70, 71, 72)
  AND NOT EXISTS (SELECT 1 FROM sys_role_menu rm WHERE rm.role_id = 9 AND rm.menu_id = m.id);
