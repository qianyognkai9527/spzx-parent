-- 推广计划主档的菜单（挂在「运营」parent_id=38 下，紧跟推广日报 sort_value=20）
-- 幂等：按 component 判存在，重跑不产生第二行。
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, '推广计划', 'promoPlan', 21, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu m WHERE m.component = 'promoPlan' AND m.is_deleted = 0);

-- 授权给「运营管理」角色（id=9）：没有这条，路由会被菜单过滤掉，点开就是 /#/error/promoPlan
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, m.id
FROM sys_menu m
WHERE m.component = 'promoPlan' AND m.is_deleted = 0
  AND NOT EXISTS (
    SELECT 1 FROM sys_role_menu rm WHERE rm.role_id = 9 AND rm.menu_id = m.id
  );
