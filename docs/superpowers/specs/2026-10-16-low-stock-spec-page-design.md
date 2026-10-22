# 低库存规格页面设计（2026-10-16）

## 背景与目标

1688 货源规格（`source_sku`）的库存低于阈值时需要人工补货/换货源，目前没有任何界面能看到规格级低库存。
目标：后台「运营管理」下新增「低库存规格」菜单页，按**货源商品**分组展示规格级低库存明细，纯查看 + 外跳，不做任何状态管理。

## 用户已定的口径

1. **数据源**：先只用 1688 货源规格库存（`source_sku.stock`）；淘宝侧全量 SKU 库存为二期（拦截每日 05:30 同步的接口响应解析入库），本期不做。
2. **阈值**：可调阈值（10 / 20 / 50 三档），另加固定双色预警：规格库存 **<10 红**、**10~19 橙**（红线固定 10，不随阈值变化）。
3. **处理方式**：纯查看，只提供外跳链接（1688 货源页 / 淘宝商品页），不做状态字段。
4. **位置**：「运营管理」(sys_menu id=38) 下新菜单，sort_value=22（推广计划 21 之后、AI 选词 60 之前）。

## 数据事实（2026-10-16 实测）

- `source_sku` 14824 行 / 838 个货源；stock<20 共 **1358 个规格 / 186 个货源**；<10 共 1180 个规格。
- 淘宝商品 ↔ 1688 货源映射的权威来源是 `automation/sourcing/sku_match_report.json`（4203 个淘宝商品 / 3815 个货源；368 个货源对应多个淘宝商品，最多 13 个）。
- `product_source_link` 表是抖音侧数据（platform_type=2），**不可用**。
- `source_product.source_product_url` 形如 `https://detail.1688.com/offer/{oid}.html`，5847 行中 2367 行可解析出 offer id。

## 架构

```
sku_match_report.json ──import_offer_map.py──▶ DB taobao_offer_map
isv_sku_match.py 跑完 ──UPSERT 刷新──▶                │
                                                      ▼
前端 lowStock 页 ──▶ GET /admin/lowStock/list ──▶ 现算 SQL:
                          source_sku(未删,stock<threshold)
                          JOIN source_product
                          LEFT JOIN taobao_offer_map
                          按货源分组返回
```

**不建物化结果表**（1358 行现算毫秒级，物化只换来滞后——推广日报同款结论）。

### ① 映射表 `taobao_offer_map`

```sql
CREATE TABLE taobao_offer_map (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  taobao_item_id BIGINT NOT NULL,
  offer_id BIGINT NOT NULL,
  source_product_id BIGINT NULL,          -- 导入时从 source_product_url 解析回填
  update_time DATETIME,
  UNIQUE KEY uk_item (taobao_item_id),
  KEY idx_offer (offer_id),
  KEY idx_sp (source_product_id)
);
```

- 一个淘宝商品只挂一个货源（UNIQUE `taobao_item_id`）；一个货源对应多个淘宝商品是正常态。
- `source_product_id` 在**导入时用 Python 解析** URL 回填，查询不在 SQL 里拆 URL。解析不到（新货源没采集过）留 NULL。
- 建表 SQL 落 `sql/taobao_offer_map.sql`（与 `sql/promo_plan.sql` 同目录风格）。

### ② 导入与刷新

- 新脚本 `automation/sourcing/import_offer_map.py`：读 `sku_match_report.json` 的 `items[]`，解析 `source_product_url` 建 offer_id→source_product_id 索引，`INSERT ... ON DUPLICATE KEY UPDATE` 全量 UPSERT。
- `isv_sku_match.py` 主流程结束处调用同一 UPSERT 函数（刷新失败只打日志，不影响匹配任务退出码）。

### ③ 后端只读端点

- `LowStockController` `@RequestMapping("/admin/lowStock")`，位于 `spzx-manager/controller/`，命名与 `PromoReportController` 同风格。
- `GET /admin/lowStock/list?threshold=20&keyword=&page=1&size=20`
  - `threshold` 白名单 {10, 20, 50}，非法值回 400（复用 `GlobalExceptionHandler` 的人话文案风格）。
  - `keyword` 匹配 `source_product_name`（可空）。
  - 返回 `Result<IPage<LowStockRowVo>>`（records/total，MyBatis-Plus），rows 每行：
    ```json
    {
      "sourceProductId": 123,
      "title": "货源标题（source_product_name，空则显示 offer_id）",
      "offerId": 980287802829,
      "sourceUrl": "https://detail.1688.com/offer/xxx.html",
      "taobaoItems": [1086192871521, ...],   // 来自 taobao_offer_map，可为空数组
      "lowSpecs": [ {"skuKey": "摩卡灰-2XL", "stock": 3, "price": 32.5} ],
      "minStock": 3
    }
    ```
  - SQL：`source_sku` `is_deleted=0 AND stock IS NOT NULL AND stock < #{threshold}` JOIN `source_product`（`is_deleted=0`）按 `source_product_id` 分组；`LEFT JOIN taobao_offer_map` 聚合淘宝商品 ID 列表。按 `minStock` 升序，分页按货源计数。
  - 聚合查询拆两条执行（分组的货源页 + 该页货源的规格明细），避免 GROUP_CONCAT 截断；与 `promo` 「分母为 0 出 NULL 不出 0」同类的读时现算原则。
- 新建 `LowStockMapper`（注解或 XML 跟现役风格一致）+ `LowStockService`。

### ④ 前端页面

- 菜单：`sys_menu` 插入「低库存规格」title、component=`lowStock`、parent_id=38、sort_value=22；角色授权比照推广日报（id=76）在 `sys_role_menu` 的配法。
- 页面 `views/mall/lowStock/index.vue`（组件路径比照现役 component 命名）：
  - 顶部：阈值切换（el-radio-group：10/20/50，写进 URL query，刷新不丢）+ 标题搜索框。
  - el-table 每行 = 一个货源商品：标题 / 货源链接（新窗口）/ 关联淘宝商品（每件一个新窗口外跳，未匹配显示「未匹配」）/ 最低库存 / 低规格数。
  - **展开行** = 低规格明细表：规格名（sku_key）/ 库存 / 价格；库存 `<10 红`、`10~19 橙`。
  - 纯查看，无任何操作按钮。

### ⑤ 边界

- 无 `taobao_offer_map` 映射的货源照常显示，淘宝列标「未匹配」。
- 只覆盖有规格数据的 838 个货源；其余货源等采集补齐 `source_sku` 后自然出现。
- `source_product_name` 为空时标题回退显示 offer_id。

## 测试

- `LowStockParamTest`（纯 JUnit）：阈值白名单、分页参数默认值、keyword 传空不拼条件。
- 手工验证：
  - `curl /admin/lowStock/list?threshold=20` 对数量级（货源数 186 附近、规格 1358 附近）。
  - 页面开一遍：阈值三档切换、搜索、展开行颜色、外跳链接可达。

## 不做的事（YAGNI）

- 不建低库存物化表 / 定时预计算。
- 不做库存修改、补货、换货源等任何写操作。
- 不做淘宝侧 SKU 库存数据源（二期）。
- 不做告警推送（sync_alert 体系不接）。

## 修订（2026-10-17）：只显示铺货的货源

用户反馈：页面不该出现没铺到淘宝的 1688 选品货源，且必须能看到对应的淘宝商品 ID。

- 原 §⑤「无映射的货源照常显示，标未匹配」**作废**：`selectLowStockGroups` 增加
  `AND EXISTS (SELECT 1 FROM taobao_offer_map tm WHERE tm.source_product_id = sp.id)`，
  只有铺货（有淘宝映射）的货源进页面。226 组 → **90 组**（threshold=20；10/50 档 74/112）。
- 淘宝商品 ID 本就实现（`taobaoItems` 可点外跳），此前用户看到的行全是无映射货源才显示「未匹配」。
- 覆盖边界（未变，如实说）：4190 条映射里仅 664 条能解析回 `source_product`（84% 的映射
  offer 未采集入库，无 `source_sku` 数据），这部分铺货货源的 1688 库存仍不可见，
  等采集覆盖后才会在页面出现。
- 回归钉子：`LowStockParamTest.主查询必须带铺货过滤_未铺货的货源不准混进页面`
  读 mapper XML 原文断言 EXISTS（ItemOpsParamTest 同款手法），前端 hint 文案同步改口径。

## 修订（2026-10-17 晚）：序号 + 人工处理留痕

用户需求：页面加序号；加「处理」列（下架处理 / 删除处理 / 下架SKU 三种），人工在平台侧处理完后回来打标记，防止时间久遗忘。

- 新表 `low_stock_handle`（sql/low_stock_handle.sql）：source_product_id 主键，handle_type 1=已下架 2=已删除 3=已下架SKU，handle_by/handle_time；重复标记 UPSERT 覆盖，撤销=删行。
- 端点：`POST /admin/lowStock/handle`（sourceProductId+handleType，非法值 400）、`POST /admin/lowStock/unhandle`；list 加 `handleStatus=all/pending/done`（非法回 all，仿 facet）。
- 主查询 LEFT JOIN low_stock_handle 带出 handleType/handleTime（DATE_FORMAT 字符串）。
- 前端：序号列（跨页连续）、处理列（未处理=三个按钮 / 已处理=标签+时间+撤销）、工具栏 全部/待处理/已处理 筛选（写 URL query）。
- 口径：**按钮只是留痕**——不碰库存、不碰淘宝/1688，实际下架/删除由人做。
- 测试：LowStockParamTest 8 条（handleType 三档白名单、handleFilter 仿 facet、LEFT JOIN 原文钉住）；check-consistency 13 过 0 失败。
