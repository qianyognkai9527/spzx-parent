-- 菜单重构脚本
-- 1. 重命名顶级菜单
UPDATE sys_menu SET title = '货源管理' WHERE id = 8;
UPDATE sys_menu SET title = '运营管理' WHERE id = 38;

-- 2. 货源管理子菜单调整
UPDATE sys_menu SET title = '货源厂家', component = 'supplyFactory', sort_value = 1 WHERE id = 53;
UPDATE sys_menu SET title = '货源商品', component = 'production', sort_value = 2 WHERE id = 13;
UPDATE sys_menu SET sort_value = 3 WHERE id = 9;   -- 分类管理
UPDATE sys_menu SET sort_value = 4 WHERE id = 10;  -- 品牌管理
UPDATE sys_menu SET sort_value = 5 WHERE id = 11;  -- 分类品牌
UPDATE sys_menu SET sort_value = 6 WHERE id = 12;  -- 商品规格

-- 3. 删除重复菜单
UPDATE sys_menu SET is_deleted = 1 WHERE id = 40;  -- 工厂信息(重复，已移至货源管理)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 55;  -- 订单关联(重复，保留订单货源关联)

-- 4. 运营管理子菜单重命名和排序
UPDATE sys_menu SET title = '平台商品', sort_value = 1 WHERE id = 37;
UPDATE sys_menu SET sort_value = 2 WHERE id = 39;  -- 历史标题
UPDATE sys_menu SET sort_value = 3 WHERE id = 34;  -- 刷单人员
UPDATE sys_menu SET sort_value = 4 WHERE id = 35;  -- 买家秀人员
UPDATE sys_menu SET sort_value = 5 WHERE id = 50;  -- 补单管理
UPDATE sys_menu SET sort_value = 6 WHERE id = 51;  -- 退款报表管理
UPDATE sys_menu SET sort_value = 7 WHERE id = 52;  -- 退款报表关联订单
UPDATE sys_menu SET sort_value = 8 WHERE id = 41;  -- 分配买家秀
UPDATE sys_menu SET sort_value = 9 WHERE id = 36;  -- 图片空间
UPDATE sys_menu SET sort_value = 10 WHERE id = 43; -- 报表录入

-- 5. 删除无对应路由的菜单
UPDATE sys_menu SET is_deleted = 1 WHERE id = 17;  -- 订单列表(无路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 7;   -- 地区管理(无路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 6;   -- 商品单位(无路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 15;  -- 会员列表(无路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 21;  -- 操作日志(无路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 46;  -- SKU(隐藏路由)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 5;   -- 基础数据管理(子菜单全删)
UPDATE sys_menu SET is_deleted = 1 WHERE id = 14;  -- 会员管理(子菜单全删)

-- 6. 推广计算和计划移至系统管理
UPDATE sys_menu SET parent_id = 1, sort_value = 8 WHERE id = 48;  -- 推广计算
UPDATE sys_menu SET parent_id = 1, sort_value = 9 WHERE id = 49;  -- 计划

-- 7. 订单管理排序
UPDATE sys_menu SET sort_value = 1 WHERE id = 18;  -- 订单统计
UPDATE sys_menu SET sort_value = 2 WHERE id = 54;  -- 订单货源关联

-- 8. 系统管理排序
UPDATE sys_menu SET sort_value = 1 WHERE id = 2;   -- 用户管理
UPDATE sys_menu SET sort_value = 2 WHERE id = 3;   -- 角色管理
UPDATE sys_menu SET sort_value = 3 WHERE id = 4;   -- 菜单管理
UPDATE sys_menu SET sort_value = 4 WHERE id = 44;  -- 字典管理
UPDATE sys_menu SET sort_value = 5 WHERE id = 45;  -- 字典数据
UPDATE sys_menu SET sort_value = 6 WHERE id = 47;  -- 日程管理
