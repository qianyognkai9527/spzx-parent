-- kw_init.sql : AI选词推广助手 表结构 + 菜单
-- 库: db_spzx

CREATE TABLE IF NOT EXISTS kw_wordbank_batch (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL COMMENT '批次名，如 睡衣女冬-0918',
  platform_type TINYINT DEFAULT 1 COMMENT '1淘宝 2抖音',
  file_names VARCHAR(500) COMMENT '来源文件名，逗号分隔',
  word_count INT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255)
) COMMENT '词表批次';

CREATE TABLE IF NOT EXISTS kw_wordbank_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  search_popularity INT COMMENT '搜索人气',
  click_rate DECIMAL(8,4) COMMENT '点击率',
  conv_rate DECIMAL(8,4) COMMENT '点击转化率',
  buyer_count INT COMMENT '买家数',
  score DECIMAL(8,4) COMMENT '加权总分',
  UNIQUE KEY uk_batch_kw (batch_id, keyword),
  KEY idx_batch_score (batch_id, score)
) COMMENT '词表词条';

CREATE TABLE IF NOT EXISTS kw_product_analysis (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  platform_type TINYINT,
  title VARCHAR(100),
  images JSON COMMENT '送AI的图片url列表',
  ai_desc JSON COMMENT '产品拆分描述JSON',
  note VARCHAR(500) COMMENT '用户补充说明(材质/人群等)',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_product (product_id)
) COMMENT 'AI识品结果';

CREATE TABLE IF NOT EXISTS kw_select_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  batch_id BIGINT NOT NULL,
  analysis_id BIGINT COMMENT '识品结果id，重试时非空则跳过识品',
  note VARCHAR(500) COMMENT '用户补充说明',
  status TINYINT DEFAULT 0 COMMENT '0待跑 1识品中 2选词中 3完成 4失败',
  error_msg VARCHAR(500),
  text_provider VARCHAR(50) COMMENT '本次选词用的引擎',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  finish_time DATETIME,
  KEY idx_status (status)
) COMMENT '选词任务';

CREATE TABLE IF NOT EXISTS kw_task_word (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  match_score INT COMMENT 'AI匹配度0-100',
  bank_score DECIMAL(8,4) COMMENT '词表得分',
  reason VARCHAR(200) COMMENT 'AI理由',
  picked TINYINT DEFAULT 0 COMMENT '用户勾选',
  KEY idx_task (task_id)
) COMMENT '任务匹配词';

CREATE TABLE IF NOT EXISTS kw_title_suggestion (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  title VARCHAR(60) NOT NULL,
  reason VARCHAR(300),
  picked TINYINT DEFAULT 0 COMMENT '用户勾选'
) COMMENT '标题优化建议';

CREATE TABLE IF NOT EXISTS kw_config (
  config_key VARCHAR(50) PRIMARY KEY,
  config_value VARCHAR(50) NOT NULL,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT 'AI引擎运行时配置';

-- 当前引擎（默认全走 tokens-store）
INSERT IGNORE INTO kw_config (config_key, config_value) VALUES ('text_provider', 'tokens-store');
INSERT IGNORE INTO kw_config (config_key, config_value) VALUES ('vision_provider', 'tokens-store');

-- 菜单（父菜单 38=运营管理；component 存前端路由 name）
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词商品', 'kwProduct', 60, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwProduct');
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词词表', 'kwWordbank', 61, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwWordbank');
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词任务', 'kwTask', 62, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwTask');

-- 授权 admin 角色(role_id=9)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, id FROM sys_menu WHERE component IN ('kwProduct','kwWordbank','kwTask')
AND id NOT IN (SELECT menu_id FROM sys_role_menu WHERE role_id=9);

-- ============ 2026-09-20 provider 定义入库（spec: docs/superpowers/specs/2026-09-20-llm-provider-config-design.md）============

CREATE TABLE IF NOT EXISTS kw_provider (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL COMMENT '唯一标识，创建后不可改（任务快照按 name 引用）',
  base_url VARCHAR(200) NOT NULL,
  api_key VARCHAR(500) NOT NULL DEFAULT '' COMMENT '明文本地存储，与原yml等级一致，不入git',
  vision_model VARCHAR(100) DEFAULT '',
  text_model VARCHAR(100) DEFAULT '',
  image_model VARCHAR(100) DEFAULT '' COMMENT '预留：子项目B生图模型，本期不读',
  max_tokens INT DEFAULT 4096,
  extra_body VARCHAR(1000) COMMENT 'JSON对象字符串，如 {"thinking":{"type":"disabled"}}',
  status TINYINT DEFAULT 1 COMMENT '1启用 0停用',
  remark VARCHAR(255),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name)
) COMMENT 'AI provider 定义（运行时配置源）';

-- 菜单：运营管理(38)下，AI选词三页面(65-67)之后；写死 id=68（当前空闲）
INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 68, 38, 'AI引擎配置', 'kwConfig', 63, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'kwConfig');

-- 授权 admin 角色(role_id=9)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, 68
WHERE NOT EXISTS (SELECT 1 FROM sys_role_menu WHERE role_id = 9 AND menu_id = 68);
