-- videogen_init.sql : AI短视频生成 表结构 + provider扩展 + 菜单
-- 库: db_spzx
-- 注意：首行 ALTER 非幂等，仅执行一次；若报 Duplicate column name 'video_model' 说明列已存在，跳过该行执行其余即可

ALTER TABLE kw_provider ADD COLUMN video_model VARCHAR(64) DEFAULT NULL COMMENT '视频生成模型编号';

CREATE TABLE IF NOT EXISTS video_gen_task (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  product_id BIGINT UNSIGNED NOT NULL COMMENT 'platform_product.id',
  prompt VARCHAR(2000) NOT NULL COMMENT '最终提交的视频提示词',
  prompt_source TINYINT NOT NULL DEFAULT 1 COMMENT '1=AI生成 2=人工编辑',
  model VARCHAR(64) NOT NULL COMMENT 'Ark模型编号',
  duration TINYINT NOT NULL DEFAULT 5 COMMENT '秒5|10',
  ratio VARCHAR(8) NOT NULL DEFAULT '9:16',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '0排队 1已提交 2生成中 3成功 4失败',
  remote_task_id VARCHAR(64) DEFAULT NULL,
  object_key VARCHAR(256) DEFAULT NULL COMMENT '成片MinIO键',
  error_msg VARCHAR(500) DEFAULT NULL,
  finish_time DATETIME DEFAULT NULL,
  create_by BIGINT UNSIGNED, create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT NOT NULL DEFAULT 0,
  KEY idx_product (product_id), KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI短视频生成任务';

-- 菜单（父菜单 38=运营管理；AI选词页面 sort 60-63 之后；component 存前端路由 name）
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI短视频', 'videogen', 64, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='videogen');

-- 授权 admin 角色(role_id=9)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, id FROM sys_menu WHERE component='videogen'
AND id NOT IN (SELECT menu_id FROM sys_role_menu WHERE role_id=9);
