# 真实盈亏数据采集设计（淘宝订单 / 1688代发 / 阿里妈妈账户花费）

- 日期：2026-10-12
- 状态：待评审（设计稿）
- 目标：把 **2024-10 ~ 2026-09**（24 个月）三份数据采下来并落库 `db_spzx`，用于计算"到底亏了多少钱"，并识别"无 1688 关联单 = 刷单"。

## 1. 背景与目标

一件代发模式：淘宝店「Sweet Baby甄选 / 茎肛葫芦娃q」每出一单，在 1688 下对应代发单。要算真实盈亏：

```
真实盈亏 = (淘宝实收 − 退款) − 1688采购成本 − 阿里妈妈推广花费
```

**刷单识别**：一笔淘宝订单在 1688 找不到对应的代发单 → 判为刷单，**不计入真实成交金额**（成本/推广费照算）。

## 2. 数据源（三份）

### 2.1 淘宝订单（已卖出宝贝）
- 页面：`https://myseller.taobao.com/home.htm/trade-platform/tp/sold`
- 两个视图（页面顶部 LI 标签，按精确文本点击）：
  - **「3个月前」**：历史订单，页面提示"可查询、导出到 **2026-07-15** 前的所有订单"。实测可查回 2024-10（2024Q4 有数据）。
  - **「近3个月」**：覆盖 2026-07-15 ~ 今天。
- 时间筛选：`创建时间` 是阿里 Fusion `next-range-picker`，**只读但面板内可打字**：
  - 点 `input[placeholder="起始日期"]` → 面板出现 `.next-range-picker-panel-input-start-date input` / `.next-range-picker-panel-input-end-date input` → 分别 `fill` 日期 → `Enter` → `Escape` 关面板。
- 查询按钮：`button` 文本 **「搜索订单」**（历史视图里取最后一个）。
- 行字段（表头 `宝贝 / 单价 / 数量 / 履约/售后状态 / 交易状态 / 实收款 / 操作`；每行是一个大 `td`，字段嵌在里面）：
  - 订单号（行文本 `订单号：...`）、创建时间（`.sold_create-time__*`）、买家（脱敏 `t**`，部分"号码保护订单"）
  - 商品标题、规格（颜色分类/尺码）、单价、数量
  - **履约/售后状态**（退款成功 / 退货宝 / …）、**交易状态**（交易成功 / 交易关闭 / …）、**实收款**

### 2.2 1688 代发订单（ISV 分销工作台）
- 页面：`https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818`
  - 业务在 iframe：`page.1688.com/html/isv-container.html?...&appId=pc-pc_work-pc_work_plugin-2839818#/order/list`
- 状态 tab：`全部 / 待采购 / 待打单 / 待发货 / 已发货 / 退款中 / 已成功 / 已关闭 / 已忽略`
- 搜索项含 **「店铺订单号」（=淘宝订单号）**，但它是"批量添加"弹层（最多 10 条），自动化下时序不稳 → **不逐单搜，改为「全部」翻页全量拉**（等价且更稳）。默认下单时间起点 = **2024-10-18**。
- 行字段（每行一个大 `td`）：
  - 店铺订单号 `a[title="店铺订单号"]`（链接 `trade.taobao.com/...biz_order_id=xxx`，确认其就是淘宝订单号）
  - 下单时间、退款状态徽标（`.trade-order-cell-content-list-item-pic-refund-status`，如"退款成功"）
  - 淘宝商品标题、`¥`淘宝售价、1688商品ID（`ID：<span class="order-id">`）、规格、数量
  - **采购单状态**（已关闭 / 已成功）、**采购金额 `￥x（含运费￥y）`**、预估利润
  - 收货地址（脱敏）、备注（采购下单备注 / 买家备注 / 卖家备注）
- 注意事项：每次查询后弹「密文提示」modal，需点「确定」关闭；CDP 在长时间/多标签后易出 `Browser context management is not supported`，需重启 9222。

### 2.3 阿里妈妈推广花费（账户层每日）
- 万相台 `one.alimama.com`，账户报表按日（可复用现有 `automation/tb-auto/collect_alimama_promo.py` 的登录/读取方式）。
- 细度：**账户每日汇总**（只要 charge，够算盈亏）。

## 3. 落库（灌进现有表）

Python 直连 `db_spzx`（`from dbconf import DB_CONFIG`；淘宝账号/店铺用 `sourcing/shop_ref.py` 的 `default_shop_id`，平台淘宝=1）。所有写库幂等（先查后插 / upsert）。

| 采集 | 目标表 | 映射 |
|---|---|---|
| 淘宝订单 | `order_info`（platform_type=1，shop_id=淘宝店） | order_no=订单号；total_amount=实收款；order_status=交易状态映射；create_time；receiver_*（脱敏）；remark 存"履约/售后状态" |
| 淘宝订单明细 | `order_item` | order_id↔order_info.id；sku_name=规格；sku_price=单价；sku_num=数量 |
| 1688 代发单 | `order_source_relation` | order_no=店铺订单号(淘宝号)；source_order_no=1688采购单号；platform_type=1；platform_product_id=淘宝商品ID；platform_product_title；platform_selling_price=淘宝售价；source_product_id=货源ID；source_product_title；source_selling_price=采购单价；source_freight=运费；order_status=采购单状态映射；order_time=下单时间 |
| 阿里妈妈账户每日 | `promo_cost_daily` | shop_id；platform_code；stat_date；report_source='account'；charge=花费；其余指标（若有） |

> `order_info`/`order_source_relation` 缺的字段（淘宝"履约/售后状态"、实收已退款额等）先塞 `remark`，不新增列；若后续分析需要再单独提。

## 4. 关联与刷单

- **关联键 = 淘宝订单号**。`order_source_relation.order_no`(淘宝) ↔ `source_order_no`(1688) 天然承载。
- **刷单判定**：某淘宝订单号 `∈ order_info(platform_type=1)` 但 `∉ {order_source_relation.order_no}` → 候选刷单。
- **输出**：阶段一只产出**清单**（JSONL + 控制台摘要：订单号、创建时间、金额、标题、交易状态），**暂不写 `brush_order`**（那是用户手工补单台账，确认口径后再定）。

## 5. 采集器形态

- 位置：`automation/tb-auto/`（三个都走 9222；`collect_alimama_promo.py` 已在此）
- 语言/依赖：Python 3.9 + Playwright async + `connect_cdp(9222)`（统一入口，禁裸 `connect_over_cdp`）
- **纯只读平台**：只读页面/翻页/打字设条件，绝不点任何"提交/导出/打单/退款/采购"按钮
- 断点续跑：进度文件（已采窗口/页）记 JSON，续跑跳过
- CLI：`--dry-run`（只读不写库）、`--from`/`--to`（日期范围，默认 2024-10-01~今天）、`--limit`（调试限量）

### 5.1 淘宝订单采集流程
1. 打开 sold 页
2. **历史段**：切「3个月前」→ 对每个 3 个月窗口（`2024-10-01 ~ 2024-12-31`、`2025-01-01 ~ …` … 到 `2026-04-01 ~ 2026-07-14`）设 `创建时间` → 搜索 → 逐页抓 → 落 `order_info`/`order_item`
3. **近期段**：切「近3个月」→ 不设区间（或设 2026-07-15~今天）→ 逐页抓
4. 幂等：`order_no` 已存在则更新

### 5.2 1688 代发单采集流程
1. 打开 ISV 页，等 iframe 就绪，关闭密文 modal
2. 点「全部」tab → 查询 → 逐页抓所有行 → 解析 → 写 `order_source_relation`
3. 每条同时记录"店铺订单号"，供刷单判定集合使用

### 5.3 阿里妈妈账户每日
1. 复用现有登录态（9222），进入账户报表
2. 按日抓 charge → 写 `promo_cost_daily`（report_source='account'）

## 6. 验证

- 每个采集器首跑用 `--dry-run --limit` 目视校验解析字段（数量、金额、状态、关联键）
- 交叉核对：淘宝 `已卖出宝贝` 某窗口条数 ≈ 抓取行数；1688「全部」计数 ≈ 抓取行数
- 落库后 SQL 抽查：`order_info` platform_type=1 近 3 月条数、`order_source_relation` 关联数、`promo_cost_daily` 覆盖 24 个月
- 刷单清单：与 `brush_order` 现有手工记录比对，看是否吻合

## 7. 未决 / 风险

1. **1688 采购单号**在 ISV 行里的准确位置待定（行里有"ID：<order-id>"疑似货源ID；采购单号可能在"采购日志/预览"或行内其它 span）——实现时先 dry-run 打印原始行全文确认。
2. 淘宝 `order_info` 无"实收已退款额/售后台账"专列，先入 `remark`；若分析需要"净实收"再议加列。
3. `order_source_relation` 的 `platform_product_id` 目前来源为 ISV 行里的淘宝商品ID，未必等于平台商品库 ID，可能需要二次映射。
4. 淘宝历史视图是否有单窗口/查询条数上限、翻页上限，实现时验证；若超限则缩小窗口。
5. 9222 headless 易掉淘宝登录态 → 采集器运行时保持**窗口模式 + 屏外位置**（`--window-position=-32000,-32000`），不弹窗打扰。
6. 阿里妈妈账户报表能否一次取 24 个月/是否按段，实现时验证。

## 8. 补充（2026-10-13）：订单权威 item_id 回填

**背景**：商品级退款绩效表最初用「标题→item_id」归集订单，改过标题的商品会把同一 item 的订单漏计 → 退款率虚高。

**结论**：淘宝卖家页里**任意订单的权威 item_id 只有一个稳定来源**——
`trade.taobao.com/trade/detail/tradeSnap.htm?tradeID=<订单号>&snapShot=true` 内嵌 JSON 的
`itemSnapDO.itemId`（普通 GET + `Referer: myseller.taobao.com/.../sold` 即返回，约 0.1s/单）。
已卖出宝贝列表 / 订单详情页**均不暴露 item_id**（只有标题、商家编码）；退款页的 `商品ID` 只覆盖退款单。

**落地**：
- `order_item` 加列 `item_id VARCHAR(64)`（`sql/order_item_item_id.sql`）。
- `automation/tb-auto/collect_order_item_ids.py`：按 order_no 逐单 GET 快照页抽 `itemSnapDO.itemId`，
  幂等 UPDATE `order_item.item_id`，进度 `order_item_ids_progress.json`。
  - 只回填付费单（`order_status IN (1,2,3)`）；**交易关闭单没有快照**，其 item_id 由 `refund_order.item_id` 提供。
  - 实测 1674 付费单命中 **1202**（72%），472 单无快照（旧壳「暂时不提供查看该宝贝的信息」，含「邮费专用」）。
- `refund_product_report.py` 重写：分母按订单解析的 item_id（**快照 → 退款 → 标题兜底**），分子按同键归集，保证分子⊆分母。
- 2024-10-01 起结果：有效 **1965**（=1674 status3 + 343 关闭带退款 − 52 刷单）/ 退款 355 / 秒退 137 /
  支付 317450.23 / 退款 94901.26 / 利润 222548.97；未映射仅 106 单（97 为邮费专用）。
  （旧标题口径只 1747 单——因 2026-04+ 订单无标题被整批漏掉。）

## 9. 补充（2026-10-14）：ISV 商品管理全量映射重采 + 盈亏报表接入

**背景**：`pnl_2026_report.py` 的 offer→item 映射仅来自 `order_source_relation×order_item`（17 offers），
逐单采购成本只配到 41/119（2026），刷单嫌疑被稀疏映射撑到 313 单。

**根因（2026-10-14 实测）**：
- 旧产物 `automation/sourcing/isv_offer_taobao_map.jsonl`（994 对）是默认关键词「甲」筛出来的、**非全量**
  —— 不含"甲"的铺货商品（外套/派克服/手链等）全漏，对 2026 在途+成功采购 offer 命中 **0/119**。
- ISV 后台已改版 **v3.5.51**：侧栏收起 + 菜单重组，「商品管理」在 **分销铺货 flyout**（订单列表在
  订单管理 flyout）；收起态下 JS click 与 Playwright 常规 hover 均**失效**，须 `hover(force=True)`
  于 `.ant-menu-submenu-title` + 真点击 flyout 项。
- 商品管理比"销售中"视图大：快捷筛选 `销售中(995)/仓库中(3183)/已关联货源(4173)`；完整映射集=已关联货源。
- **SPA 筛选 chip 跨会话残留**（残留的货源ID筛选把 `--ids` 查询毒成 0 行）→ 每次先点「重置」。
- 货源ID/关键词输入框多在「更多」折叠后 `visible=False` → Playwright `fill` 拒填隐藏元素（曾把 3-sid
  批量查变成抓回整 tab 991 行）→ 必须用**原生 setter + input 事件**绕过可见性。
- 个别行行内/`a[href*=detail.1688.com/offer/]` 都不渲染货源ID（多为"关联货源已下架"）→ 单sid补查、
  唯一行以查询的 sid 归属。

**落地**：
- `automation/sourcing/scrape_isv_offer_taobao.py` 重写：新 UI 导航、`select_tab(已关联货源)`、先重置、
  `--offers` 按 50/批精查 + 未覆盖的**单sid补查**、`--keyword` 默认空(全量)、**合并写**(按 taobao_item_id，
  新行覆盖旧行，不丢已删商品的旧对)、`if __name__` 守卫（此前导入即跑）。
- 覆盖：采购单里共 **281** 个 distinct offer，其中 **226 个**在商品管理查无（共0条=从未铺货/已删/无关联，
  无映射可采，属数据边界）；合并后 jsonl **1985 行**（1983 对有 offer）。
- `pnl_common.merge_offer_items(osr_pairs, jsonl_pairs)`：OSR(订单时点)在前 ∪ ISV商品管理(现绑定)去重，
  同 offer 多 item 全保留；报表 `pnl_2026_report.py` 新增 `--isv-map`（默认 ../sourcing/isv_offer_taobao_map.jsonl）。
  单测 `automation/tb-auto/test_pnl_isv_map.py`。
- **结果**：映射 OSR 17 + ISV 1983 对 → 1983 offers / 冲突 9；逐单配到采购 **2026 82/119**（旧 41）、
  **全窗口 155/410**（旧 97）；2026 未归属成本 ¥1914.33（旧 ¥4735.73）；刷单嫌疑 **272 单**（旧 313）。
  **真实盈亏不变**（映射只影响归属，不动总额）：2026 **+¥40,100.52**、2024-10 起 **+¥193,734.00**。
- 未做：ISV 订单列表行级补采（原可选方案），视后续覆盖需要再定。

