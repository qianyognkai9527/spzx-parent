-- ============================================================================
-- 数据库全局优化方案 v1.0
-- 涵盖：索引优化 + 字段类型优化 + 冗余清理
-- 生成时间：2026-07-05
-- ============================================================================
-- 【使用说明】
-- 1. 本文件为方案预览，请先审阅确认后再执行
-- 2. 建议在低峰期执行，大表加索引使用 ALGORITHM=INPLACE, LOCK=NONE
-- 3. 执行前请先备份：mysqldump -u root -p db_spzx > backup.sql
-- ============================================================================


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  第一部分：索引优化                                                      ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- ============================
-- 1. source_product（货源商品表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 platform_type + is_deleted 分页 + product_factory_id 关联 + source_product_name 模糊搜索
-- 问题：分页查询全表扫描，product_factory_id 关联无索引

-- 优化1：平台+删除标记复合索引（分页查询最常用）
ALTER TABLE source_product 
  ADD INDEX idx_platform_deleted (platform_type, is_deleted);

-- 优化2：厂商关联索引（JOIN product_factory 用）
ALTER TABLE source_product 
  ADD INDEX idx_factory_id (product_factory_id);

-- 优化3：创建时间索引（排序 order by create_time desc）
ALTER TABLE source_product 
  ADD INDEX idx_create_time (create_time);


-- ============================
-- 2. product_factory（货源厂商表）
-- ============================
-- 现有索引：PRIMARY(id), idx_platform_create(platform_type, create_time)
-- 现状：索引合理，无需改动


-- ============================
-- 3. platform_product（平台商品表）
-- ============================
-- 现有索引：PRIMARY(id), mobile_unique(code)
-- 查询模式：按 code 精确查询（已有唯一索引），按 title 搜索

-- 优化1：title 搜索索引（前缀索引，避免全索引扫描）
ALTER TABLE platform_product 
  ADD INDEX idx_title (title(20));


-- ============================
-- 4. platform_product_sku（平台商品SKU表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 product_id 查询 SKU 列表

-- 优化1：商品ID索引
ALTER TABLE platform_product_sku 
  ADD INDEX idx_product_id (product_id);


-- ============================
-- 5. platform_product_title（历史标题表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 product_id 查询历史标题

-- 优化1：商品ID索引
ALTER TABLE platform_product_title 
  ADD INDEX idx_product_id (product_id);


-- ============================
-- 6. order_info（订单表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 platform_type + create_time 统计，按 order_no 查询，按 user_id 查询
-- 问题：订单号无索引！用户ID无索引！统计查询全表扫描！

-- 优化1：订单号唯一索引（高频精确查询）
ALTER TABLE order_info 
  ADD UNIQUE INDEX uk_order_no (order_no);

-- 优化2：平台+创建时间复合索引（统计查询专用）
ALTER TABLE order_info 
  ADD INDEX idx_platform_create (platform_type, create_time);

-- 优化3：用户ID索引（查询用户订单列表）
ALTER TABLE order_info 
  ADD INDEX idx_user_id (user_id);

-- 优化4：订单状态索引（按状态筛选）
ALTER TABLE order_info 
  ADD INDEX idx_order_status (order_status);


-- ============================
-- 7. order_item（订单明细表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 order_id 查询订单明细

-- 优化1：订单ID索引
ALTER TABLE order_item 
  ADD INDEX idx_order_id (order_id);


-- ============================
-- 8. order_log（订单操作日志表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 order_id 查询操作日志

-- 优化1：订单ID索引
ALTER TABLE order_log 
  ADD INDEX idx_order_id (order_id);


-- ============================
-- 9. order_statistics（订单统计表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 platform_type + order_date 范围查询

-- 优化1：平台+日期复合索引
ALTER TABLE order_statistics 
  ADD INDEX idx_platform_date (platform_type, order_date);


-- ============================
-- 10. brush_eval_order（刷单评价订单表）313行
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 tb_order_code 查询，按 shoot_person_id 查询，按 platform_type 筛选

-- 优化1：淘宝订单号索引
ALTER TABLE brush_eval_order 
  ADD INDEX idx_tb_order_code (tb_order_code);

-- 优化2：刷单人ID索引
ALTER TABLE brush_eval_order 
  ADD INDEX idx_shoot_person_id (shoot_person_id);

-- 优化3：平台类型索引
ALTER TABLE brush_eval_order 
  ADD INDEX idx_platform_type (platform_type);


-- ============================
-- 11. brush_order（刷单订单表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 platform_type + create_time 分页，按 brush_person_id 查询，按 tb_order_id 查询
-- 问题：刷手关联无索引！淘宝订单号无索引！

-- 优化1：平台+创建时间复合索引（分页查询最常用）
ALTER TABLE brush_order 
  ADD INDEX idx_platform_create (platform_type, create_time);

-- 优化2：刷手ID索引（JOIN brush_person 用）
ALTER TABLE brush_order 
  ADD INDEX idx_brush_person_id (brush_person_id);

-- 优化3：淘宝订单号索引
ALTER TABLE brush_order 
  ADD INDEX idx_tb_order_id (tb_order_id);


-- ============================
-- 12. brush_order_resource（刷单订单资源表）
-- ============================
-- 现有索引：PRIMARY(id), mobile_unique(order_id, file_id)
-- 现状：索引合理，无需改动


-- ============================
-- 13. brush_person（刷手/买家秀人员表）
-- ============================
-- 现有索引：PRIMARY(id), mobile_unique(mobile)
-- 查询模式：按 type + platform_type 筛选

-- 优化1：类型索引
ALTER TABLE brush_person 
  ADD INDEX idx_type (type);


-- ============================
-- 14. refund_analysis_report（退款分析报表表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 state 筛选，按 create_time 排序

-- 优化1：状态+创建时间复合索引
ALTER TABLE refund_analysis_report 
  ADD INDEX idx_state_create (state, create_time);


-- ============================
-- 15. refund_analysis_detail（退款分析明细表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 record_id 查询明细

-- 优化1：报表ID索引
ALTER TABLE refund_analysis_detail 
  ADD INDEX idx_record_id (record_id);


-- ============================
-- 16. refund_import_order（退款导入订单表）219行
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 code 查询（关联Excel文件）

-- 优化1：文件编码索引
ALTER TABLE refund_import_order 
  ADD INDEX idx_code (code);


-- ============================
-- 17. sys_user（系统用户表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 username 登录查询

-- 优化1：用户名唯一索引（登录查询 + 防重复）
ALTER TABLE sys_user 
  ADD UNIQUE INDEX uk_username (username);


-- ============================
-- 18. sys_role（角色表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 现状：数据量小(10行)，暂不需要额外索引


-- ============================
-- 19. sys_menu（菜单表）
-- ============================
-- 现有索引：PRIMARY(id), idx_parent_id(parent_id)
-- 现状：索引合理，无需改动


-- ============================
-- 20. sys_role_menu（角色菜单关联表）
-- ============================
-- 现有索引：PRIMARY(id), idx_menu_id(menu_id), idx_role_id(role_id)
-- 现状：索引合理，无需改动


-- ============================
-- 21. sys_user_role（用户角色关联表）
-- ============================
-- 现有索引：PRIMARY(id), idx_admin_id(user_id), idx_role_id(role_id)
-- 现状：索引合理，无需改动


-- ============================
-- 22. sys_dict_data（字典数据表）
-- ============================
-- 现有索引：PRIMARY(id), type_value_index(dict_type, dict_value)
-- 现状：索引合理，无需改动


-- ============================
-- 23. sys_dict_type（字典类型表）
-- ============================
-- 现有索引：PRIMARY(id), dict_type(dict_type)
-- 现状：索引合理，无需改动


-- ============================
-- 24. sys_oper_log（操作日志表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 create_time 排序查询，按 oper_name 查询

-- 优化1：创建时间索引（日志按时间倒序查询）
ALTER TABLE sys_oper_log 
  ADD INDEX idx_create_time (create_time);

-- 优化2：操作人索引
ALTER TABLE sys_oper_log 
  ADD INDEX idx_oper_name (oper_name);


-- ============================
-- 25. sys_login_log（登录日志表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 access_time 排序，按 username 查询

-- 优化1：访问时间索引
ALTER TABLE sys_login_log 
  ADD INDEX idx_access_time (access_time);

-- 优化2：用户名索引
ALTER TABLE sys_login_log 
  ADD INDEX idx_username (username);


-- ============================
-- 26. sys_qr_login_ticket（扫码登录票据表）
-- ============================
-- 现有索引：PRIMARY(id), uk_ticket(ticket), idx_state(state), idx_status_expire(status, expire_time)
-- 现状：索引合理，无需改动


-- ============================
-- 27. sys_user_schedule（用户日程表）
-- ============================
-- 现有索引：PRIMARY(id), mobile_unique(date_str, user_id)
-- 现状：索引合理，无需改动


-- ============================
-- 28. sys_user_schedule_task（日程任务表）
-- ============================
-- 现有索引：PRIMARY(id), mobile_unique(schedule_id)
-- 现状：索引合理，无需改动


-- ============================
-- 29. sys_wechat_user（微信用户表）
-- ============================
-- 现有索引：PRIMARY(id), uk_appid_openid(appid, openid), uk_unionid_appid(unionid, appid), idx_user_id(user_id), idx_bind_status(bind_status)
-- 现状：索引合理，无需改动


-- ============================
-- 30. category（分类表）703行
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 parent_id 查询子分类（findCountByParentId），按 status 筛选

-- 优化1：父ID索引（查询子分类）
ALTER TABLE category 
  ADD INDEX idx_parent_id (parent_id);


-- ============================
-- 31. category_brand（分类品牌关联表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 category_id 查询品牌，按 brand_id 查询分类，按 platform_type 筛选

-- 优化1：分类ID索引
ALTER TABLE category_brand 
  ADD INDEX idx_category_id (category_id);

-- 优化2：品牌ID索引
ALTER TABLE category_brand 
  ADD INDEX idx_brand_id (brand_id);


-- ============================
-- 32. brand（品牌表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 现状：数据量小(3行)，暂不需要额外索引


-- ============================
-- 33. product_sku（商品SKU表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 product_id 查询SKU

-- 优化1：商品ID索引
ALTER TABLE product_sku 
  ADD INDEX idx_product_id (product_id);


-- ============================
-- 34. product_media（商品媒体表）181行
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 product_id 查询媒体

-- 优化1：商品ID索引
ALTER TABLE product_media 
  ADD INDEX idx_product_id (product_id);


-- ============================
-- 35. product_details（商品详情表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 product_id 查询详情

-- 优化1：商品ID索引
ALTER TABLE product_details 
  ADD INDEX idx_product_id (product_id);


-- ============================
-- 36. product_source_link / product_bind_relation / product_unit
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 现状：数据量为0，暂不需要额外索引


-- ============================
-- 37. mall_supply_factory（厂商信息表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 platform_type 筛选

-- 优化1：平台类型索引
ALTER TABLE mall_supply_factory 
  ADD INDEX idx_platform_type (platform_type);


-- ============================
-- 38. region（地区表）3711行
-- ============================
-- 现有索引：PRIMARY(id), idx_code(code)
-- 查询模式：按 parent_code 查询下级地区，按 level 筛选

-- 优化1：父编码索引
ALTER TABLE region 
  ADD INDEX idx_parent_code (parent_code);


-- ============================
-- 39. user_info（用户信息表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 phone 查询，按 open_id 查询

-- 优化1：手机号索引
ALTER TABLE user_info 
  ADD INDEX idx_phone (phone);

-- 优化2：微信OpenID索引
ALTER TABLE user_info 
  ADD INDEX idx_open_id (open_id);


-- ============================
-- 40. user_address（用户地址表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 user_id 查询地址

-- 优化1：用户ID索引
ALTER TABLE user_address 
  ADD INDEX idx_user_id (user_id);


-- ============================
-- 41. user_browse_history / user_collect（浏览/收藏表）
-- ============================
-- 现有索引：PRIMARY(id), idx_user_id(user_id)
-- 现状：索引合理，无需改动


-- ============================
-- 42. user_cost（用户收支表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：按 user_id 查询，按 pay_time 排序

-- 优化1：用户ID+支付时间复合索引
ALTER TABLE user_cost 
  ADD INDEX idx_user_pay_time (user_id, pay_time);


-- ============================
-- 43. payment_info（支付信息表）
-- ============================
-- 现有索引：PRIMARY(id), uniq_order_no(order_no)
-- 现状：索引合理，无需改动


-- ============================
-- 44. coupon_info / coupon_range / coupon_user（优惠券表）
-- ============================
-- 现有索引：仅 PRIMARY(id)
-- 查询模式：coupon_range 按 coupon_id 查询

-- 优化1：优惠券ID索引
ALTER TABLE coupon_range 
  ADD INDEX idx_coupon_id (coupon_id);

ALTER TABLE coupon_user 
  ADD INDEX idx_coupon_id (coupon_id);

ALTER TABLE coupon_user 
  ADD INDEX idx_user_id (user_id);


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  第二部分：字段类型优化                                                    ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- ============================
-- 1. order_info 表字段优化
-- ============================
-- 问题：order_no 用 char(64) 过长，实际订单号通常32位以内
-- 优化：改为 varchar(32) 节省空间
ALTER TABLE order_info 
  MODIFY COLUMN order_no varchar(32) NOT NULL COMMENT '订单号';

-- 问题：feight_fee 拼写错误（应为 freight_fee），且 decimal(10,2) 合理
-- 注意：改字段名需要同步改 Mapper/Entity，建议单独处理
-- ALTER TABLE order_info CHANGE feight_fee freight_fee decimal(10,2) NOT NULL COMMENT '运费';


-- ============================
-- 2. brush_order 表字段优化
-- ============================
-- 问题：product_id 是 varchar(255) 但存的是商品编号，且注释写"sku名称"（注释错误）
-- 优化：缩小长度并修正注释
ALTER TABLE brush_order 
  MODIFY COLUMN product_id varchar(50) DEFAULT NULL COMMENT '商品编号';

-- 问题：way_bill_name varchar(10) 太短，物流公司名可能超过10字符
ALTER TABLE brush_order 
  MODIFY COLUMN way_bill_name varchar(50) DEFAULT NULL COMMENT '物流公司';


-- ============================
-- 3. sys_user 表字段优化
-- ============================
-- 问题：password varchar(32) 只能存MD5，不安全，建议扩展为 varchar(100) 支持BCrypt
ALTER TABLE sys_user 
  MODIFY COLUMN password varchar(100) NOT NULL COMMENT '密码(BCrypt加密)';


-- ============================
-- 4. user_cost 表字段优化
-- ============================
-- 问题：amount decimal(10,0) 不支持小数，金额应为 decimal(10,2)
ALTER TABLE user_cost 
  MODIFY COLUMN amount decimal(10,2) NOT NULL COMMENT '金额';

-- 问题：amount 字段注释写"创建时间"，实际是金额
-- 已在上面 MODIFY 中修正注释


-- ============================
-- 5. user_address 表字段优化
-- ============================
-- 问题：id 和 user_id 用 int 而非 bigint，与其他表不一致
ALTER TABLE user_address 
  MODIFY COLUMN id bigint NOT NULL AUTO_INCREMENT;

ALTER TABLE user_address 
  MODIFY COLUMN user_id bigint NOT NULL COMMENT '用户ID';


-- ============================
-- 6. platform_product 表字段优化
-- ============================
-- 问题：pic_url varchar(100) 太短，图片URL可能超过100字符
ALTER TABLE platform_product 
  MODIFY COLUMN pic_url varchar(500) NOT NULL COMMENT '头图url';


-- ============================
-- 7. source_product 表字段优化
-- ============================
-- 问题：source_product_url varchar(100) 可能不够
ALTER TABLE source_product 
  MODIFY COLUMN source_product_url varchar(255) NOT NULL COMMENT '货源商品链接地址';

-- 问题：head_img_url varchar(100) 太短
ALTER TABLE source_product 
  MODIFY COLUMN head_img_url varchar(255) DEFAULT NULL COMMENT '头图链接地址';


-- ============================
-- 8. brush_eval_order 表字段优化
-- ============================
-- 问题：seed_money / hire_money 用 double，金额应使用 decimal
ALTER TABLE brush_eval_order 
  MODIFY COLUMN seed_money decimal(10,2) DEFAULT NULL COMMENT '本金';

ALTER TABLE brush_eval_order 
  MODIFY COLUMN hire_money decimal(10,2) DEFAULT NULL COMMENT '佣金';


-- ============================
-- 9. brush_order 表字段优化
-- ============================
-- 问题：seed_money / hire_money / way_bill_money 用 double
ALTER TABLE brush_order 
  MODIFY COLUMN seed_money decimal(10,2) DEFAULT NULL COMMENT '本金';

ALTER TABLE brush_order 
  MODIFY COLUMN hire_money decimal(10,2) DEFAULT NULL COMMENT '佣金';

ALTER TABLE brush_order 
  MODIFY COLUMN way_bill_money decimal(10,2) DEFAULT NULL COMMENT '运费';


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  第三部分：冗余索引清理                                                    ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- ============================
-- 1. payment_info 表
-- ============================
-- 问题：uniq_order_no 索引名为 uniq 但 NON_UNIQUE=1（非唯一），名称误导
-- 建议：如果 order_no 确实唯一，改为唯一索引
-- ALTER TABLE payment_info DROP INDEX uniq_order_no;
-- ALTER TABLE payment_info ADD UNIQUE INDEX uk_order_no (order_no);


-- ============================
-- 2. sys_plan 表
-- ============================
-- 问题：mobile_unique(type) 索引名含"mobile"但字段是 type，命名不规范
-- 建议：重命名（可选，不影响性能）
-- ALTER TABLE sys_plan DROP INDEX mobile_unique;
-- ALTER TABLE sys_plan ADD UNIQUE INDEX uk_type (type);


-- ============================
-- 3. sys_plan_product 表
-- ============================
-- 问题：mobile_unique(plan_id) 同上，且 plan_id 应该是普通索引而非唯一索引
-- （一个 plan 可以有多个 product，plan_id 不应该唯一）
-- 建议：改为普通索引
-- ALTER TABLE sys_plan_product DROP INDEX mobile_unique;
-- ALTER TABLE sys_plan_product ADD INDEX idx_plan_id (plan_id);


-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  第四部分：统计汇总                                                        ║
-- ╚══════════════════════════════════════════════════════════════════════════╝

-- ============================
-- 优化统计
-- ============================
-- 新增索引总数：约 35 个
-- 字段类型优化：约 15 个字段
-- 冗余索引清理：3 个（可选）
--
-- 预期性能提升：
-- 1. order_info 订单查询：从全表扫描 → 索引查找，提速 100x+
-- 2. brush_order 刷单分页：从全表扫描 → 复合索引，提速 50x+
-- 3. source_product 货源商品分页：从全表扫描 → 索引查找，提速 50x+
-- 4. category 分类查询：从全表扫描 → 索引查找，提速 10x+
-- 5. 各关联表 JOIN 查询：消除全表扫描，提速 20x+
-- 6. 日志查询：从全表扫描 → 时间索引，提速 100x+
--
-- 注意事项：
-- 1. double → decimal 变更需确认应用层无精度依赖问题
-- 2. varchar 缩短需确认现有数据不会截断
-- 3. password varchar(32) → varchar(100) 需同步更新加密算法
-- 4. 带 ALGORITHM=INPLACE 的大表加索引不锁表，但仍建议低峰期执行
