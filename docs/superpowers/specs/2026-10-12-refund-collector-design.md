# 退款数据采集设计（淘宝退款管理 → 真实退款率/退款额）

- 日期：2026-10-12
- 状态：待评审（设计稿）
- 目标：把淘宝「退款管理」页的逐条售后/退款记录采下来落库，得到**平台口径的真实退款率、退款额**，支持**按售后类型 / 按商品**拆解，并**自动喂给现有"退款分析"模块**（替代手工传 Excel）。

## 1. 背景与目标

现状：现有「退款分析」模块（`refund_analysis_report` / `refund_analysis_detail` + `MallRefundRecordServiceImpl`）**依赖人工上传 Excel**（`OrderSimpleExcelBo` → `refund_import_order` 表，仅 `order_id/pay_money/refund_money/order_status` 四个业务列）。它算得出退款率/利润，但：
- 数据要手工导出/上传，滞后且易错；
- 没有「售后类型」「商品」维度，看不出**哪类售后、哪个商品**最伤。

用户诉求（4 条全要）：
1. 平台口径的**真实退款率 / 退款额**（整体，可按月、按售后类型看趋势）
2. 定位**哪个商品 + 哪类售后最伤**
3. **替代手工传 Excel**（自动把退款数据喂进现有模块）
4. 以上都要

## 2. 数据源：淘宝「退款管理」

- 页面：`https://myseller.taobao.com/home.htm/trade-platform/refund-list`
- **售后类型 tab**（精确文本，逐类抓）：`全部售后 / 退款（不含退货） / 未发货退款 / 未收货退款 / 已收货退款 / 退货退款 / 维修 / 换货 / 补寄 / 退运费`
- 子视图标签：`最近申请` / `历史退款`（历史视图用于回溯）
- **日期筛选**：`起始日期` / `结束日期` 两个输入框 + `搜索售后单` 按钮
- 表格列（表头）：`商品信息 | 金额信息 | 售后原因及件数 | 快递信息 | 售后状态/协商/纠纷 | 操作`
- 分页：`上一页 / 下一页`
- 顶部还有 `待处理售后 / 需关注售后 / 售后单统计 / 售后单查询` 等入口

**只读铁律**：只允许点「售后类型 tab / 日期框 / 搜索售后单 / 重置换筛选 / 翻页 / 历史退款子标签」。
**绝不点**：`同意退款 / 同意退货 / 备注 / 导出 / 智能退款工具 / 一键开通极速售后` 等任何写操作或导出按钮。

> ✅ 保留期已实测（2026-10-12）：退款页可回溯至约 **2023-07-01**（2023Q2 及更早分季度查询返回空）。
>   `collect_refund_orders.py` 用常量 `RETENTION_START=2023-07-01` 作为默认 `--from`，覆盖全部可查范围。
>   （设计原定 `2024-10-01`；实测保留更早，已按实测放宽。）

## 3. 落库（方案 3：权威新表 + 派生喂旧模块）

### 3.1 新表 `refund_order`（权威逐条明细）

| 列 | 类型 | 说明 |
|---|---|---|
| id | bigint PK auto | |
| platform_type | tinyint | 1=淘宝 |
| shop_id | bigint | |
| refund_no | varchar(64) | **退款编号/售后单号**（唯一键之一） |
| order_no | varchar(32) | 子订单号/订单号（与 `order_info.order_no` 对齐） |
| after_sale_type | varchar(32) | 售后类型（未发货退款/退货退款/…） |
| status | varchar(32) | 售后状态（退款成功/等待卖家同意/…） |
| refund_amount | decimal(10,2) | 退款金额 |
| order_amount | decimal(10,2) | 订单金额/付款金额 |
| apply_time | datetime | 申请时间 |
| finish_time | datetime | 完结时间（可空） |
| reason | varchar(255) | 售后原因 |
| product_title | varchar(255) | 商品标题 |
| sku_name | varchar(255) | 规格 |
| item_id | varchar(64) | 商品 ID（有则存） |
| buyer_nick | varchar(100) | 买家（脱敏） |
| raw_json | text | 原始行文本（排错用） |
| create_time / update_time | datetime | |
| unique key | `uk_refund_no (platform_type, refund_no)` | 幂等 upsert |

> `refund_no` 若页面拿不到，退化为 `(platform_type, order_no, after_sale_type, apply_time)` 组合键——实现 dry-run 时确认。

### 3.2 派生写入现有 `refund_import_order`（喂旧模块）

按 `order_no` 聚合 `refund_order`，派生一行写 `refund_import_order`：
- `order_id = order_no`
- `refund_money = Σ refund_amount`（该订单所有售后）
- `pay_money = order_amount`（该订单付款额）
- `order_status` 映射：有退款且 `Σ退款额 ≥ 订单额` → `交易关闭`；有退款但未全退 → `卖家已发货，等待买家确认`；无退款 → `交易成功`
- `platform_type / shop_id` 同源

> 写 `refund_import_order` 前先删该 `shop_id+platform_type` 下"由本采集器派生"的行（打标：用一个约定 `code` 前缀，或先删后插整个来源），避免与手传 Excel 行重复。实现时确认打标方式。

### 3.3 分析面（满足 #1/#2）

**阶段一先出只读 SQL 视图 / 轻量只读接口，前端页面另议**：
- 按月：退款单数、退款额、退款率（退款单/成交单）
- 按售后类型：各类占比与金额
- 按商品：top 退款商品（退款单数/额）
- 与 `order_info`（成交单）联算真实退款率

## 4. 采集器形态

- 位置：`automation/tb-auto/collect_refund_orders.py`（走 9222，`connect_cdp(9222, keep_urls=[...])`）
- 语言/依赖：Python 3.9 + Playwright async；纯只读平台；DB 直连 `dbconf.DB_CONFIG`
- 复用 `pnl_common.py` 的 `log/parse_money/parse_dt/connect_db`
- 断点续跑：进度文件 `refund_progress.json`（已采 `售后类型 + 日期窗口`）
- CLI：`--dry-run`（只读不写库）、`--from/--to`（默认 `2023-07-01`(实测保留起点)`~今天`）、`--limit`、`--max-pages`、`--types`（默认全部售后类型）
- 退出码：0 成功；命中风控/结构异常非 0（便于 cron 判失败）

## 5. 验证

- dry-run：打印每条退款记录（退款编号/订单号/售后类型/退款额/状态/申请时间/商品），目视校验字段与页面一致
- 交叉核对：某售后类型 tab 的「共 N 条」≈ 抓取行数；pilot 一个日期窗口
- 落库后 SQL：`refund_order` 覆盖的日期范围、按售后类型分布、按订单聚合与 `refund_import_order` 派生一致性
- 与 `refund_import_order` 现有 219 行手工数据抽样比对（同为"交易关闭"的订单，退款额是否吻合）

## 6. 未决 / 风险

1. **退款页保留期** —— 实测可回溯至约 2023-07-01（2023Q2 及更早为空）；默认 `--from=2023-07-01` 覆盖全保留范围。
2. **退款编号 `refund_no` 是否稳定可抓** —— 决定唯一键；拿不到则用组合键。
3. **行结构（两行/一行、单元格下标）** —— 由实现时 dry-run 打印原始行确认（与淘宝订单采集器同套路）。
4. **`refund_import_order` 派生行的"打标/清理"方式** —— 避免与手传 Excel 行冲突，需先删后插或加来源标记；确认后再实现。
5. **抓取节奏与风控** —— 与淘宝写任务共用账号；退款采集是只读但翻页多，需限速、按 tab/窗口断点续跑。
6. **自动化（每日 cron）** —— 放最后，先手动跑通。
