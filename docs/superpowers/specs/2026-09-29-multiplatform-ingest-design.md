# 多平台可扩展架构与拼多多接入设计

日期：2026-09-29
状态：待评审（纯设计，未落地代码）
范围：spzx-parent（Java 后端 + automation Python 采集）与 spzx-admin（Vue 前端）的平台维度改造，拼多多作为第一个按新契约接入的平台。

## 1. 背景

系统当前服务淘宝和抖店，能力分散在 Java 单体（`spzx-manager`）和 automation 下的 Playwright 脚本里。业务侧要接拼多多，且店铺规模会从"每平台 1 店"走向"每平台 2-5 店"。

直接加"第 3 个平台"会让已有的结构问题翻倍，所以本次不是加功能，而是先把**平台/店铺这两个维度做成有主键、有契约的东西**，再接拼多多。

## 2. 目标与非目标

目标

- 加一个平台的成本从"改 326 处常量"降到"插 1 行配置 + 写 N 个数据映射器"。
- 平台侧数据带店铺维度，同平台多店不再串数据。
- 采集入库有统一契约：幂等、可观测、可重放。
- 拼多多第一波只回流数据（订单/售后/商品/日指标/推广），不做写动作。

非目标（明确不做）

- 不重新编号现有平台值：`1=淘宝 2=抖音` 保留，拼多多 `=3`。
- 不为拼多多新建一套平行的商品/订单表；沿用并补齐现有表。
- 不做多租户/权限隔离，不做店铺级数据隔离。
- 不在 Java 侧启动 Python 采集进程。
- 不碰发货、客服、物流回传。
- 不引入微服务拆分（`docs/ARCHITECTURE.md` 那份蓝图不在本设计范围）。

## 3. 现状事实（本设计的依据）

- `spzx-model/.../enums/PlatformTypeEnum.java` 只定义 `TAOBAO(1)`、`DOUYIN(2)`。
- `platform_type` 出现在 **139 个文件 / 326 处**（Java、Mapper XML、Python）。
- 前端另抄两份：`src/constants/dict.js` 的 `PLATFORM_DICT = {1:淘宝, 2:抖音}`、`src/views/home/index.vue` 的 `PLATFORM_COLORS = {1:…, 2:…}`。
- 11 个 Python 脚本直接 `INSERT` 业务表：`platform_product`、`source_product`、`source_sku`、`source_factory`、`order_info`、`sku_bind_relation`、`sync_alert`、`inventory_change_log`、`source_product_sales_history`、`sycm_item_effect_history`、`novel_chapter`。去重逻辑各写各的（`INSERT` 与 `REPLACE INTO` 混用）。
- 4 张表只存在于 Python 的 INSERT 语句里，Java 侧没有实体，schema 无人负责：`sycm_item_effect_history`、`source_product_sales_history`、`source_sku`、`inventory_change_log`。
- `platform_product_title` / `platform_product_sku` / `product_media` 有 `product_id` 外键，可派生归属。
- `refund_analysis_report` 没有 `product_id`，商品归属靠 `code`（货号字符串）+ `order_data_code` 匹配；`refund_analysis_detail` 连 code 都没有。**派生不出店铺归属**。
- `platform_type` 在父表和 5 张子表（title/sku/media/refund_report/refund_detail）重复存储，存在父子不一致的空间。
- P0 落地时新发现：`order_info`（43 行）、`refund_import_order`（219 行）、`refund_analysis_report`（4 行）的 `platform_type` **全部为 NULL**，即历史订单与退款数据不知道自己属于哪个平台；`order_bind` 是空表，推不出归属。`platform_product`（4679 行）则 1/2 分布正常。这是一个先于本次改造存在的数据缺陷。
- `platform_product` 的唯一索引实际名为 `mobile_unique`（历史遗留命名），列是 `code`；`order_info` 有 `uk_order_no(order_no)` 全局唯一。

## 4. 设计决策

| 编号 | 决策 | 理由 |
|---|---|---|
| D1 | 平台与店铺改为数据库注册表，代码读取，不再各自硬编码 | 收敛 326 处的唯一办法是把值挪走 |
| D2 | 保留 `1/2` 数值语义，拼多多取 `3` | 全表重编码成本不可接受 |
| D3 | `shop_id` 只加在"店级事实"表，派生子表不加 | 双写店 ID 迟早和父表不一致 |
| D4 | 采集侧统一走 `batch + raw + normalizer` 契约 | 幂等、可重放、字段变更不需重抓 |
| D5 | 快照覆盖顺序由纯函数决定，不埋在 SQL 里 | 该逻辑可单测 |
| D6 | 平台回改的金额落独立结算表，不覆盖订单原始金额 | 防止利润分析随重抓漂移 |
| D7 | Java 是 schema 与语义唯一 owner，Python 只写 batch/raw | 接口窄到两张表，加平台在采集侧只剩抓取 |
| D8 | 采集调度留在系统 cron，后端只做新鲜度监控与告警 | 抓取依赖桌面 Chrome 登录态，服务不该 spawn 进程 |
| D9 | 子表冗余 `platform_type` 保留，但加一致性校验单测锁住 | 删除改动面大且不阻塞拼多多（默认方案） |

## 5. 数据模型

DDL 为设计草案，落地时另出迁移脚本。

### 5.1 注册表

```
platform(
  code           TINYINT PRIMARY KEY,   -- 1 taobao / 2 douyin / 3 pinduoduo
  slug           VARCHAR(32) UNIQUE,    -- Python 目录名、枚举名、前端 key 用它
  name           VARCHAR(32),           -- 前端展示名的唯一来源
  theme_color    CHAR(7),               -- 看板颜色唯一来源
  money_channel  VARCHAR(32),           -- alipay | platform_settlement
  enabled        TINYINT DEFAULT 1
)

shop(
  id             BIGINT PK AUTO,
  platform_code  TINYINT,
  shop_name      VARCHAR(64),
  outer_shop_id  VARCHAR(64) NULL,      -- 平台侧店铺 ID
  ingest_channel ENUM('api','browser','export'),
  credential_ref VARCHAR(128) NULL,     -- 只存"指向哪"：local 配置 key 或 profile 目录名
  cdp_port       INT NULL,
  status         TINYINT,
  first_online_at DATE NULL,
  UNIQUE(platform_code, shop_name)
)

platform_capability(
  platform_code  TINYINT,
  capability     VARCHAR(32),           -- ingest_order / ingest_after_sale / ingest_item_metric
                                       -- ingest_promo_cost / publish_product / attach_media ...
  supported      TINYINT,
  channel        VARCHAR(16) NULL,
  note           VARCHAR(255) NULL,
  PRIMARY KEY(platform_code, capability)
)
```

约束：凭据明文永不入库，`credential_ref` 只是引用。能力矩阵驱动前端入口显隐，替代 `if (platformType == 2)`。

### 5.2 shop_id 的落点

加（店级事实与店级运维）

- `platform_product`、`order_info`、`refund_import_order`
- `refund_analysis_report`、`refund_analysis_detail`（因归属派生不出，见 D3 例外）
- `sync_alert`
- 新表：`ingest_batch`、`ingest_raw`、`platform_item_daily`、`platform_sku_stock`、`promo_cost_daily`、`platform_order_settlement`

不加（由 `platform_product` / `order_info` 派生）

- `platform_product_title`、`platform_product_sku`、`product_media`、`product_factory`、`product_source_link`、`product_bind_relation`、`sku_bind_relation`
- `brush_order`、`brush_eval_order`、`brush_order_resource`
- `profit_analysis_record`、`kw_*`、`video_gen_task`、`expense_*`、`novel*`
- 1688 货源侧全部：`source_product`、`source_sku`、`source_factory`、`product_details` 等（上游，跨平台复用）

派生例外说明：`expense_*` 属于收款主体维度，拼多多是平台结算不是支付宝，其店铺归属在 P2 与利润口径一起处理，本次不动。

聚合表说明：`order_statistics` 现按 `province_code × order_date × platform_type` 聚合，由 `OrderStatisticsTask` 重算。店维度通过给聚合加 `shop_id` 分组实现，属于**改聚合**，不是给派生表加列回填。

两张容易混的 SKU 表：`source_sku` 是 1688 货源侧 SKU（属于上游，不加 shop_id，收编方式是补 Java 实体与 mapper）；`platform_sku_stock` 是平台店铺在售 SKU 的库存快照（新表，天然带 shop_id）。两者不合并，也不是同一张表的改名。

### 5.3 迁移与回填

设计原文的三步中，第三步（唯一索引改造）在 P0 实际**没有执行**，理由与结果如下：

1. 各表 `ADD shop_id BIGINT NULL` + `ADD INDEX (shop_id)`。已执行。
2. 每个平台插入一条 `is_default=1` 的默认店，回填 `platform_product`（4679 行全部命中，1/2 两平台）。已执行，前后对账行数与金额合计一致。
3. `order_info` / `refund_import_order` / `refund_analysis_report` / `refund_analysis_detail` 因 `platform_type` 为 NULL，**shop_id 保持 NULL，不做任何编造**。归属需要一条单独的数据修复任务（人工确认"这 43 单属于哪个平台"这类规则，或等新采集契约天然带上）。
4. 唯一索引不动：`platform_product` 的 `mobile_unique(code)` 与 `order_info` 的 `uk_order_no(order_no)` 保持原样。原本设计的 `(shop_id, code)` 会让 `code` 从"全局唯一"变成"每店唯一"，而 Java 侧存在按 code 查询的路径（如 `refund_import_order.idx_code`、退款分析的 code 匹配），在真正出现第二个店之前放宽它是无收益的风险。等第二个店落地时再连同 code 查询路径一起改。
5. `shop_id` 的 NOT NULL 约束推迟到 P1（采集契约强制写入后再收紧），避免 P0 因漏改某个写入点直接把自动化脚本打挂。

## 6. 采集契约

```
ingest_batch(
  id, platform_code, shop_id, dataset, channel,
  biz_from DATE, biz_to DATE,                    -- 业务时间窗，非抓取时间
  rows_total INT, rows_ok INT, rows_dup INT, rows_invalid INT,
  status ENUM('queued','running','success','partial','failed'),
  fingerprint CHAR(32),                          -- shop+dataset+窗口+来源指纹，用于去重
  error TEXT, started_at, finished_at
)

ingest_raw(
  id, batch_id, natural_key VARCHAR(128),
  payload JSON, fingerprint CHAR(32),
  status ENUM('pending','normalized','invalid'),
  error TEXT,
  UNIQUE(batch_id, natural_key)
)

ingest_dataset(                                  -- 契约元数据，Java 侧拥有
  code VARCHAR(32) PK,                           -- order / after_sale / item / item_daily / promo_cost
  target_table VARCHAR(64),
  natural_key_cols VARCHAR(128),
  required_cols VARCHAR(255),
  sla_hours INT                                  -- 超期未成功入库即告警，见第 8 节
)
```

流程

1. Python 抓取 → 按 `shop + dataset + 窗口 + fingerprint` 建或复用 batch → 逐行写 raw。窗口重叠是设计意图（防漏），重复由自然键消化。
2. Java `IngestNormalizer`（定时 + 页面手动触发）按 `(platform, dataset)` 选择 RowMapper，把 raw 洗成目标事实表的 upsert。
3. 洗失败的行标 `invalid` 并保留原文，可通过 `POST /admin/ingest/{batchId}/replay` 重放。原始报文一直留在库里，平台改字段时改映射器重放即可，不必重抓。

幂等与自然键

| dataset | 自然键 | 覆盖策略 |
|---|---|---|
| order | `(shop_id, platform_order_sn)` | 快照单调：仅当 incoming 更新才覆盖状态 |
| after_sale | `(shop_id, after_sales_id)` | 快照单调 |
| item | `(shop_id, goods_id)` | 直接覆盖（当前态） |
| item_daily | `(shop_id, goods_id, stat_date)` | 直接覆盖（报表终态） |
| promo_cost | `(shop_id, campaign_id, stat_date)` | 直接覆盖 |

"谁赢"的判断实现为纯函数 `SnapshotMerger.shouldOverwrite(existing, incoming)` 并单测，SQL 只做机械 upsert。

金额与关账

- 平台 T+1/T+3 回改的佣金、技术服务费、优惠承担写入 `platform_order_settlement`（增量、按结算日），**不覆盖** `order_info` 原始金额。
- 指标类字段允许覆盖；影响账单/利润的金额字段在写入前查 `ExpensePeriodService.isClosed(period)`，已关账期间的回改只落结算表并记 batch 明细，不改已核对数据。

拼多多第一波需要 5 个 RowMapper：order、after_sale、item、item_daily、promo_cost。

## 7. 边界

Java

- 拥有全部表的实体与 mapper；4 张 Python-only 表在收编后消失。
- 提供 `GET /admin/platform/list`、`GET /admin/shop/list?platform=`、ingest 相关接口。
- 负责洗数、幂等、新鲜度判定与告警。

Python（`automation/pdd-auto/`）

- 独立 CDP 端口（9224 起，避开 9222/9223）、独立 chrome-profile、独立 cron，遵守现有风控红线。
- 只写 `ingest_batch` / `ingest_raw` 两张表，不再 INSERT 业务表。
- 字段清单以 `datasets.json` 声明，供契约一致性校验读取。

前端

- `PLATFORM_DICT` 由常量改为登录后从接口拉取、缓存在 pinia；看板颜色读 `theme_color`。
- 平台/店铺下拉与 Tab 由「店铺 + capability」过滤生成。
- 入口显隐由能力矩阵决定，例如拼多多店铺不显示挂主图视频。

## 8. 错误处理与可观测

- batch `partial` 必须在列表页可见并显示 `rows_invalid`，不允许静默少数据。
- 数据新鲜度：某店某 dataset 超过 `ingest_dataset.sla_hours` 未成功入库 → Java 生成 `sync_alert`（告警所有权从 Python 收回），走已打通的钉钉通道。
- 抓取侧网络/风控失败由 Python 自行重试，不污染 batch 状态语义。
- 缺 `required_cols` 的行标 invalid，校验只在 Java 一处。

## 9. 测试策略

仓库无 CI、前端无测试框架，策略按现实定。

- **RowMapper 单测为主战场**：`IngestNormalizer` 与 5 个拼多多映射器用纯 JUnit（不拉 Spring 上下文、不联网），fixture 为脱敏 raw JSON，放 `src/test/resources/ingest/pdd/*.json`。店铺未起时先用手工构造 fixture，并在测试上标注覆盖度打折，等首单后替换真实样本。
- **纯函数单测**：`SnapshotMerger.shouldOverwrite`（新旧覆盖顺序）、金额口径换算。
- **契约一致性**：Java 单测读取 `automation/pdd-auto/datasets.json` 与 `ingest_dataset` 元数据 fixture 比对字段清单。只能半自动（本地跑）。
- **冗余维度一致性**：针对 D9，写一个校验父子表 `platform_type` 是否一致的测试或巡检 SQL。
- **迁移防线**：shop_id 回填配前后对账 SQL（行数、`SUM(金额)` 不变），脚本留 `spzx-manager/src/main/resources/sql/`，人工执行。
- 前端不假装可测：给出手工验收清单（第 11 节）。

## 10. 分期

三份分期各自独立可用，任何一步停下都不是半成品状态。**紧接的实现计划只覆盖 P0**，P1/P2 各需自己的 spec 补充与计划。

P0 结构先行（起店前可做，不碰采集）

- `platform` / `shop` / `platform_capability` 三表 + 默认店回填 + 各表加 `shop_id`。
- 前端字典与看板颜色接口化；平台下拉改为接口驱动。
- 退出条件：淘宝/抖店现有功能无回归；新增一个平台不再需要改 Java 常量。

P1 拼多多按新契约接入（有真实数据后）

- `ingest_batch` / `ingest_raw` / `ingest_dataset` + 标准事实表。
- `automation/pdd-auto/` 采集 + 5 个 RowMapper + 新鲜度告警。
- 退出条件：拼多多订单/售后/商品/日指标/推广在后台可查，重复抓取不产生脏行。

P2 老平台迁移与口径收口

- 抖店订单、生意参谋流量迁入契约。
- `order_statistics` 聚合加店维度。
- 拼多多结算口径接入利润分析；`expense_*` 与店铺归属对齐。

## 11. 验收清单（人工）

- 平台字典接口改动后，AI 选词配置页三个引擎卡与列表颜色仍正确。
- 视频成本护栏、日预算拦截在多平台下按店铺隔离计算。
- 对账关账锁定不受 shop_id 迁移影响。
- 拼多多数据入库后：重复跑同一窗口，订单行数不变、状态不回退。
- 停掉某店采集超过阈值后，钉钉收到一条该店该数据集的告警。

## 12. 风险与未决

1. 拼多多开放平台的权限与 API 覆盖面尚未核实，很可能全程走浏览器抓取；此时 `ingest_channel=browser`，架构不变，但字段稳定性更差，raw 留存价值更高。核实工作属于 spike，结论回填本节。
2. 店铺尚未开起来，P1 早期 fixture 只能手工构造，真实脱敏样本要等首单。
3. 拼多多结算口径与现有 `fee_benchmark` 利润模型不同源，P2 之前对拼多多只能出毛口径利润，页面需显式标注，不得显示为精确值。
4. 单人维护、无 CI，契约漂移靠人对齐；缓解手段只有 raw 全留 + 洗数失败可见，拦不住失误。
5. 4 张 Python-only 表收编期间，新旧两套表并存，需明确读取入口只走 Java，避免页面读到旧表而采集写新表。

## 13. 需要评审确认的点

- D9（子表冗余 `platform_type` 保留 + 一致性校验）已按默认方案写入；若改为彻底删除，需要重估 P0 改动面。
- P0 是一次交付还是拆成 P0a（建表 + shop_id 回填）与 P0b（前端字典接口化）两次上线。内容都属于 P0，这里只问上线节奏。
- `sycm_item_effect_history` 的读路径迁到 `platform_item_daily` 放在 P1 还是 P2。P1 期间老表继续由脚本写、页面继续读老表，不影响拼多多接入。

## 14. P0 执行记录（2026-09-29）

已完成并用真实接口验证：

- DDL：`sql/multiplatform_p0.sql`（`platform` / `shop` / `platform_capability` + 6 张表加 `shop_id` 与索引）。
- 种子与回填：`sql/multiplatform_p0_seed.sql`。`shop.id` 由种子显式指定为 1/2/3，保证回填值稳定——中途重灌种子若依赖 AUTO_INCREMENT，历史 `shop_id` 会指向不存在的店。
- 对账：`sql/multiplatform_p0_verify.sql`，迁移前后 `platform_product` 4679 行 / ¥475631.91、`order_info` 43 行 / ¥209018.00、`refund_import_order` 219 行 / ¥6361.15 均未变化。
- Java：`entity/platform/{Platform,Shop,PlatformCapability}`、三个 mapper、`service/platform/PlatformRegistryService`（含纯函数 `pickDefaultShop`）、`controller/PlatformController`（`GET /admin/platform/{list,enabled,shop/list,capability}`）、`PickDefaultShopTest`（8 个用例全绿）。
- 自动化：`automation/sourcing/shop_ref.py` 提供 `default_shop_id` / `shop_id_of_product`；`crawl_douyin_orders.py`、`create_douyin_product.py`、`detect_alerts.py` 的写入已带 `shop_id`。取不到店铺时返回 None，不伪造归属。
- 前端：`api/platform.js`、`pinia/modules/platform.js`、`constants/dict.js` 的 `mergePlatforms`（原地补全 `PLATFORM_DICT` 与 `platformOptions`，已 import 它们的页面无需逐页改造）、`permission.js` 登录后加载一次。接口不可用时回退本地兜底字典。`npm run build` 与 eslint 通过。

执行中发现并修掉的两个问题：

1. **中文双重编码**：本机 MySQL 的 `character_set_client` 默认是 `latin1`，首次用 mysql CLI 灌种子导致库里存进的是错字节，Java 侧读出 `æ·˜å®` 乱码。修正方式是所有脚本必须带 `--default-character-set=utf8mb4` 执行，已写进 SQL 文件头。校验：`SELECT HEX(name) FROM platform WHERE code=1` = `E6B798E5AE9D`（正确的 UTF-8 "淘宝"）。
2. **只读接口泄露内部配置**：`GET /admin/platform/shop/list` 原本直出 `Shop` 实体，把 `credential_ref` 和 `cdp_port` 发给任何登录用户。已在 `PlatformRegistryService.listShops` 里清空这两个字段，实测返回均为 null。

P0 尾巴（2026-09-29 补齐，浏览器实测）：

- 看板 `views/home/index.vue` 的饼图颜色改读 `platform.colorOf(platformType)`，本地常量降级为 `FALLBACK_PLATFORM_COLORS`。
- `components/PlatformTabs.vue` 的 Tab 由 `platform.platforms` 生成（原来是硬编码两个 `el-tab-pane`），9 个页面共用该组件，无需逐页改。
- `pinia/modules/platform.js` 收窄到实际被消费的成员（`platforms/loaded/loading/colorOf/load`）。店铺列表接口保留在 `api/platform.js`，等 P1 的店铺筛选再接。
- 实测证据（dev 服务器 + 8501 后端 + in-app 浏览器）：
  - 网络面板：`/admin/platform/enabled` 在 `/admin/system/index/menus` 之前发出，守卫接线正确。
  - `UPDATE platform SET enabled=1 WHERE code=3` → 刷新后 Tab 从「淘宝/抖音」变成「淘宝/抖音/拼多多」，切过去显示「暂无数据」且无报错；随后已还原 `enabled=0`。入口显隐确实由注册表驱动，不是前端常量。
  - 平台商品列表（淘宝 Tab）加载 10 行 / 共 3110 条，无错误提示。
- 未做：饼图切片的像素级颜色核对。内嵌浏览器 surface 是 0×0 隐藏视口，echarts 容器宽高为 0，canvas 取不到像素；`colorOf` 的数据源（enabled 接口带 `themeColor`）已由网络面板证实。

## 15. 全项目代码审查（2026-09-29，三个子代理 + 逐条复核）

后端 / 前端 / 接口契约各派一个只读审查代理，结论我逐条回代码与运行时核实。**已修**：

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| 1 | `sync_alert.notified` 只在本机手工加过列，仓库里没有 DDL。换库即 `Unknown column 'notified'`，告警列表与推送任务一起挂 | `SHOW CREATE TABLE sync_alert` 有列，`grep notified sql/` 无命中 | 新增 `sql/sync_alert_notify_channel.sql`（NOT NULL DEFAULT 0 + 复合索引），并说明 Python 侧 INSERT 不写这列、靠默认值兜底，所以不能允许 NULL |
| 2 | P0 建表在 latin1 下执行，17 处中文列/表注释双重编码（`æ‰€å±žåº—é“º`） | `information_schema.COLUMNS` 的 `HEX(COLUMN_COMMENT)` 以 C3 开头；行数据本身正常（`HEX(name)`=E6B798） | 新增并执行 `sql/multiplatform_p0_fix_comments.sql`，复核 bad_comments=0，platform/shop 数据与 4679 行 `shop_id` 未受影响 |
| 3 | 视频日预算是「读合计→判断→插行」三步，无并发保护，双击/两标签页可同时通过 → Ark 实扣翻倍 | `VideoGenTaskService.guardBudget` | `budgetLock` 串行化 guard+insert（单实例进程内锁，注释写明多实例需换 DB 计数器行） |
| 4 | `attachToProductMedia` 用两次独立 JdbcTemplate 调用取 `LAST_INSERT_ID()`，不同连接 → 返回 0 或别人的 id | `VideoGenTaskService:343-349` | 方法加 `@Transactional`，两次调用同连接 |
| 5 | 批量建任务里被队列拒绝的任务仍算进 `created`/`estCostTotal`，前端「已创建 N 个 / 预计扣 ¥X」虚报 | `createBatch` 拒绝分支只标 FAIL | 拒绝 id 移出 `created` 并入 `skipped` |
| 6 | 番茄状态文件（Python 直写）键非章号或值为 null 时，章节列表整页 500（`Integer.valueOf` / NPE） | `NovelChapterServiceImpl:41-43` | 过滤 `value != null && key.matches("\\d+")` |
| 7 | 批量生成的提示词未限长，超 `VARCHAR(2000)` 写库报错（视觉模型产出长度不可控） | `run()` 回写 prompt 无限长校验 | 统一 `PROMPT_MAX_LEN`，超长截断；`create()` 的 2000 字面量也换成该常量 |
| 8 | 字典类型/字典值的删除按钮指向不存在的接口 | 运行时 `NoResourceFoundException`；`SysDictTypeController` 只有 page/insert/update | 补 `DELETE /admin/system/dictType/removeById/{id}`（带「还有 N 个字典值」前置校验）和 `DELETE /admin/dictData/delete/{id}`。实测：有子值时返回 204+中文原因，清空后 200；自检用的临时行已删除，`sys_dict_type` 仍 5 行、`sys_dict_data` 仍 28 行 |
| 9 | `platform_product.create_by/update_by` 是 `varchar(64)`，实体 `MallProduct` 声明 `Long` → 任一行存了非数字，整张表的分页查询报 `NumberFormatException`，页面显示「您的网络有问题请稍后重试」 | 实测：平台商品列表报 9999，后端日志 `Error attempting to get column 'create_by' ... For input string: "vgtest"`（视频联调留下的测试商品 4722） | 新增并执行 `sql/platform_product_audit_columns_fix.sql`：非数字置 NULL（不删任何业务行，测试商品与其 25 条视频任务记录都保留）后收敛为 BIGINT。复核：行数仍 4679，列类型 bigint，页面恢复 10 行/3110 条、拼多多 Tab 显示「暂无数据」且无 toast |
| 10 | SKU 维护 / 历史标题 / 买家秀三页调用后端必填 `platformType` 的接口时没带该参数，选了商品也必定加载失败 | 实测对照：`productSku/all?productId=1` → 9999；带 `&platformType=1` → 200。三个 service 都把它当查询条件（`eq(...::getPlatformType, platformType)`） | 前端补传所选商品的 `platformType`（`api/productSku.js`、`api/productTitle.js`、`picture.vue`） |
| 11 | keep-alive 页面切走后，在途请求的 `finally` 会把轮询定时器重新点着；轮询失败还会再弹一次 toast（`silent` 只是页面局部变量，没进 axios config） | `kw/task/index.vue` `schedule()`、`videogen/index.vue` `startPolling()` | 两处加 `active` 开关（`onDeactivated/onUnmounted` 置 false），并给 `GetKwTaskPage`/`GetVideoTaskPage` 增加 `config` 透传，后台轮询传 `{silent:true}` |
| 12 | 看板 8 个接口用 `Promise.all` + 空 catch：一个挂掉整页清零，且每分钟自动刷新最多弹 8 条提示 | `home/index.vue loadAll` | 改 `Promise.allSettled` 逐项赋值，失败的项保留上一次数据；自动刷新传 `{silent:true}`（`api/dashboard.js` 七个接口 + `GetExpenseStatsDaily` 支持 config） |
| 13 | 章节页把筛选写进 URL 时只写了 `novelId`/`fanqieStatus`。keep-alive 的 key 是 `route.fullPath`，query 一变组件就重挂 → 标题与状态筛选被清空，且 `refresh()` 打在垂死实例上 | `Content/index.vue:55` + `novelChapter.vue syncUrl` | 四个筛选项全量进出 URL；URL 真变了就交给重挂后的首屏请求，没变才手动 `refresh()` |
| 14 | 章节页 ProTable 的子组件 `onMounted` 早于父组件，首屏请求按「全部小说」发出后默认书才定下来 → 下拉显示第一本书、表格却是所有书的章节 | `novelChapter.vue:704-716` | 定下默认书后补一次 `pageNum=1 + refresh()` |
| 15 | 看板切走时 resize 监听还挂着，`chart.resize()` 在脱离文档的 0×0 容器上重算，切回来一片空白 | `home/index.vue:587-623` | 监听随 `onActivated/onDeactivated` 摘挂，切回主动 `handleResize()` |
| 16 | `/kw/provider/video-price` 的注释声称同时改日预算，实际 DTO 只有 `videoPrice`（前端改预算走 `/kw/config` 的 `videoDailyBudget`） | `KwProviderController:241-262` | 改正注释 |

审查里被我说服不动的几条，理由记下来免得下次再吵：

- **预算合计包含 FAIL 任务**：宁高勿低是刻意的。区分「是否真的提交过 Ark」（`remote_task_id` 是否为空）才能不计失败任务，代价是把保守方向打开；失败重试也会重复占用额度，同样偏保守，符合实际扣费风险。
- **`retry()` 再走一次 guardBudget**：行已存在，`todaySpended()` 里本就含它，只会更严不会漏。
- **KwAiClient 对任意 RuntimeException 降级**：主用引擎配置坏了时降级反而让批次跑得完，日志有 `kw降级到备用引擎`；最坏耗时 `2×N×timeout` 是有意的可用性取舍。
- **`markAllRead` 不置 `notified`**：`status` 是"人已读"，`notified` 是"已推送"，两件事。
- **三个上传 `on-success` 里的 `response.code === 200`**：那是 el-upload 自己的 XHR，拿到的是原始响应体，不过 `request.js` 信封，不是契约违规。
- **`visualScore.vue` 的「淘宝主图/抖音主图/1688选品头图」**：三个 Tab 不全是平台维度，换成注册表驱动会丢第三个入口。

仍然挂着的：

- `parse1688` 前端在调但后端不存在（利润分析「解析1688链接」永远失败），口径待你定，见 §18 的 A/B/C。`api/product.js` 已在 §18-3 删除。
- P1 采集层的**契约与监控部分已落地（§19）**：三张表 + `ingest_dataset` + 新鲜度告警 + 任务进度页面板。仍未开始的是拼多多侧的 5 个 RowMapper 与 `automation/pdd-auto/`，等店铺起量与开放平台可行性核实。

## 16. 三项决议的落地（2026-09-29）

1. **测试数据保留**：商品 4722 与其 25 条 `video_gen_task` 记录不删。崩溃源已在 §15-9 通过列类型收敛消除，留着这些数据不再影响页面，且保住了那笔真实花费的台账。

2. **历史单归属**：`sql/backfill_platform_type_taobao.sql` 把 `order_info`(43)、`refund_analysis_report`(4)、`refund_import_order`(219)、`refund_analysis_detail`(2) 的 `platform_type` 填 1、`shop_id` 填 1（淘宝默认店）。批次明细按 `refund_import_order.code = refund_analysis_report.order_data_code` 跟随所属报表，再对孤儿行兜底。对账：行数与金额一字未变（43 / ¥209018.00、219 / ¥6361.15、4 / ¥44716.38、2），四张表 `platform_type=1` 与 `shop_id=1` 的命中数等于总行数。

   **归属依据是业务确认，不是数据推导**——脚本头部记下了三条查不到的交叉验证路径：`order_info.order_no` 关联 `order_source_relation` 命中 0 行；`refund_import_order.code` 与 `platform_product.code` 命中 0 行（它是报表批次码，4 个值分别是 31/47/45/96 行）；`order_bind` 是空表。

   顺这条路查下去发现**前向链路也是断的**，比"历史没回填"更严重：

   - `views/mall/createOrder.vue`（报表录入）提交时从不带 `platformType`，表单里根本没有平台这一项；
   - `MallRefundRecordServiceImpl.submitData()` 即使拿到平台也没往下传——明细构造里只 `setCode`，从不 `setPlatformType/setShopId`；
   - `generate()` 写分析明细时同样不继承报表归属。

   即每次新导入都会再生产一批 NULL 平台数据。已修：录入页加「所属平台」必选项（选项来自 `platformOptions`，即注册表），`submitData` 缺平台直接抛 `ServiceException(500,'请选择报表所属平台')`，报表 / 批次明细 / 分析明细三处统一写 `platform_type` 与 `defaultShopId(platformType)`。`order_info` 侧不用动：Java 无写入路径，唯一写入者 `crawl_douyin_orders.py` 已显式写 `platform_type=2` + `shop_id`。

3. **状态字典集中清扫**：`constants/dict.js` 新增 `VIDEO_GEN_STATUS_DICT`、`KW_TASK_STATUS_DICT`、`FANQIE_STATUS_DICT`、`PRODUCT_ISSUE_DICT` 与 `dictColor()`；页面侧：

   - `videogen/index.vue` 删掉本地 `STATUS_MAP`，`PENDING_STATUS` 改由字典的 `pending` 标记推导（不再另抄一份 `[0,1,2]`），搜索下拉由 `toDictOptions` 派生；「生成中」转圈与「失败」tooltip 的结构保留，只把文案/颜色换成 `dictLabel`/`dictTagType`。
   - `kw/task/index.vue` 列表列与详情抽屉里两份重复的 `el-tag` 链合并为 `<dict-tag>`；轮询的"全部终态"判断从 `status===3||status===4` 改成读 `pending`，未知状态继续轮询（与改前等价）。一处可见变化：`待跑` 原来是 `el-tag` 默认色，现按字典给 `info` 灰，与短视频「排队」对齐。
   - `mall/novelChapter.vue` 番茄状态标签与筛选下拉改用 `FANQIE_STATUS_DICT`。
   - `home/index.vue` 的 `wmLabel`/`wmColor` 两条 if 链改成查 `PRODUCT_ISSUE_DICT`。

   派生结果用 Node 逐项核对，与改前一致：`PENDING=[0,1,2]`；kw 终态判断 `0/1/2→false、3/4→true、9→false`；看板问题类型 0–5 的文案与色值逐个相同（含未知值走「图片水印 / #7b2ff7」兜底）。`eslint` 与 `npm run build` 通过。
   **未做浏览器实测**：8501/3001 按你要求已停（IDEA 要用 8501），这轮只到构建级 + 派生逻辑核对。

## 17. D9 巡检与映射收口（2026-09-29）

**`sql/multiplatform_consistency_check.sql`** —— D9 的落地件。库里 41 张表带 `platform_type`、只有 6 张带 `shop_id`，子表平台值是各写入方（Java 各 service + `automation/` 下 Python 直写脚本）自己填的，没有外键也没有触发器，漂移只会慢慢显形。规则都是只读 SELECT，**每条应返回 0 行**：

- R1 子表 `platform_type` 与父 `platform_product` 不一致（`order_source_relation` / `product_media` / `platform_product_sku` / `platform_product_title` / `product_details` / `kw_product_analysis` / `brush_order`）
- R2 批次与明细跟随所属报表（`refund_import_order` 按 `order_data_code`、`refund_analysis_detail` 按 `record_id`）
- R3 `shop_id` 与 `platform_type` 指向不同平台（`shop.platform_code` 是店铺归属的唯一权威）
- R4 悬空 `shop_id`（回填脚本改过 `shop.id` 后会出这种）
- R5 出现注册表里没有的平台码
- R6 `sync_alert` 的 `shop_id` 与所关联商品的 `shop_id` 漂移
- W1 告警级：已知遗留，允许非 0，但每次要比数字有没有变大

**首跑结果（本地 db_spzx）**：R1–R6 全 0；W1 = 535。

写 R1 时踩到一个真陷阱，值得记下来：`product_source_link.product_id` 是 **varchar**，注释写着"货源链接地址"，归档脚本 `automation/sourcing/_archive_20260906/sync_isv_to_platform.py:5` 说明它存的是 `source_product.id`；而 `source_product.id` 区间 44–7677、`platform_product.id` 区间 38–4722 **完全重叠**，MySQL 又会把 varchar 静默转成数字比较，于是"误当平台商品 join"照样命中 673 行，第一次跑就报了 673 条假违规。所以这张表从 R1 移出，改成 W1：它的 `platform_type` 673 行全写死 2(抖音)，而真实父行是 535 淘宝 + 138 抖音 —— 不一致的 535 行来自已归档脚本的硬编码，活跃代码无人再写这张表。定性前不要批量 UPDATE：`MallProductLinkController` 仍在读写它，页面口径可能也按"抖音"在用。

**kind → 模型列映射收口**：原先 `KwProviderService` 里 3 份 + `KwConfigController` 里 1 份同样的 `switch (kind)`，加新 kind 要改 4 处。现在统一为 `KwProviderService.modelOf(...)`（实体版与字段版各一个重载），`ProviderDef.modelFor` 也 delegate 过去；新增 `KwProviderModelMappingTest` 4 个用例锁住"两条路径口径一致""未知 kind 落 text""缺列返回 null 由调用方判定"。

`KwProviderController` 连通测试里那句"优先 textModel、无则 visionModel"**没有**并进 `modelOf`：那是探测用的优先级选择，不是 kind 分派，换过去会改语义。

后端 `mvn compile` 通过，单测 28 个全绿（原 24 + 新 4）。

## 18. 审查遗留的三处小修 + 一处待决（2026-09-29）

1. **MinIO URL 拼接收口**：`VideoGenController` 与 `VideoGenTaskService` 各拼一次 `endpoint/bucket/objectKey`。挂载去重是按 `product_media.file_url` **逐字节**比较的，两处写法一旦分叉（补斜杠、换域名、加 https）就会重复插行且页面看不出来。现统一为 `VideoGenTaskService.objectUrl(objectKey)`，控制器改调它，自身两个 `@Value` 字段与 import 一并删除。
2. **`downloadFilename` 不再静默吞异常**：`catch (Exception ignore)` 空体改为 `log.warn` 带 `product_id` —— 退回默认命名是正确降级，但"为什么退"必须留下痕迹，否则商品编码长期失效无人察觉。控制器补 `@Slf4j`。
3. **删死文件 `spzx-admin/src/api/product.js`**：7 个导出全部 0 引用，且基路径 `/admin/product/product` 后端根本不存在（只有 `/admin/product/productUnit`、`/admin/product/sourceFactory`）。留着会让人以为这套 CRUD 已接通。文件是 git 跟踪的，需要可 `git checkout` 找回。

**待你定的一个功能口径 —— 利润分析的「解析1688链接」按钮**：

`src/api/sourceProduct.js` 的 9 个端点里 7 个真实存在，只有 `parse1688` / `import1688` 后端没有。`profitAnalysis.vue:97` 的按钮就在调 `parse1688`，所以点了必失败（还被全局异常处理包成"您的网络有问题请稍后重试"）。三条路：

| 方案 | 成本 | 风险 |
|---|---|---|
| A 摘掉按钮 + 删两个失效函数，货源价/运费走现有通路（手工填 / 选品脚本回写） | 近零 | 少一个入口，但它本来就没通过 |
| B Java 里实现抓 1688 详情页 | 1–2 天 | 新增一条抓取面，与 AGENTS.md 的 CDP 端口分工/风控红线冲突；页面结构一变就坏 |
| **C 复用 `automation/sourcing/collect_1688_full.py`（已实现"一次详情页访问拿 SKU+运费"，含下架与风控冷却判断），Java 只加一个按 offerId 回写 `platform_product.pricing/freight` 的接口** | 中（半天到一天） | 不新增风控面，符合"Python 采集 / Java 口径"的既定边界 |

我推荐 C：能力已经存在且被验证过，缺的只是把结果接进后台口径；B 是把已解决的问题再解决一遍。选定前我不动这块代码，也先保留 `Import1688Product`（无页面引用，但方案 C/A 都会决定它的去留）。

验证：`mvn compile` 通过，前端 `npm run build` 通过。

## 19. P1a 落地：采集契约三表 + 数据新鲜度告警（2026-09-29）

只做「契约 + 监控」，不做拼多多采集——那部分等真数据与开放平台核实。脚本 `sql/ingest_contract_p1a.sql`（建表+种子，可重复执行）、`sql/ingest_contract_p1a_verify.sql`（对账+自检）。

### 19.1 monitor 的准入判据（三条同时成立才置 1）

第 8 节写的「超 SLA 未成功入库就告警」在今天的现实里有个前置问题：**只有 2 个数据集能被诚实判定**。

1. 有 cron/定时调度在跑；
2. **每次成功运行都无条件写入**（"有变化才写"的事件表不行——空窗是正常状态，会被误报成挂了）；
3. 时间列只有 Python 写、**Java 不写这张表**（后台任何一次 UPDATE 都会把 `update_time` 顶成"刚采过"，等于给自己造假心跳）。

按这三条：

| dataset | 量法 | 判据 | monitor |
|---|---|---|---|
| `item_daily_sycm` → `sycm_item_effect_history.snapshot_time` | table | 每日 06:00 整批插入；Java 全库对该表只有 SELECT | 1（SLA 30h） |
| `source_sku` → `source_sku.update_time` | table | 每周六 03:00 全量重写每一行；Java 只读 | 1（SLA 192h，给周末不开机留冗余） |
| `inventory_change_log` / `sync_alert` | — | 事件表，没变化就没行 | 不入表，否则天天误报 |
| `order` / `after_sale` / `item` / `item_daily` / `promo_cost` | batch | 契约预留，`ingest_batch` 今天无人写 | 0 |

`item` 特意排除：`platform_product.update_time` 同时被后台编辑写入，当采集心跳会造假。

### 19.2 实测：静默失败是真实存在的

建表当场就抓到两次「跑挂了后台完全无感知」：

- 生意参谋商品快照最后一次成功是 **09-27 06:03**，09-28、09-29 两轮没跑——`cron_sycm_snapshot.sh` 在 9222 Chrome 不在线时 `exit 0` 静默跳过，退出码正常、日志在外人看不见，后台一行数据没进也毫无动静。判定当前 58h > 30h → 过期。
- `source_sku` 每周六全量，9 月四个周六只有 **09-05、09-26** 落下数据，09-12、09-19 两轮同样是静默跳过。

这就是 D8「后端不接管调度、只判新鲜度」要解决的问题，且不需要任何新采集代码。

### 19.3 告警的幂等语义

`ingest_dataset` 自带状态列 `stale_since` / `alerted_at`，一轮过期只告一次：

- 判到新鲜 → 若 `stale_since` 非空则清空（视为恢复，下轮再过期是新一轮）；
- 判到过期且 `stale_since` 为空 → 置为当轮时间；
- `alerted_at` 为空或早于本轮 `stale_since` → 写一条 `sync_alert`（`alert_type='ingest_stale'`，`shop_id` 取该平台默认店）并记 `alerted_at`。

告警复用 `sync_alert` + `SyncAlertNotifyTask`，**不新开通道**。顺带把该任务标题从「库存同步提醒」改为「运营提醒」——这张表现在同时承载库存类与采集新鲜度类告警，旧标题会让后者看起来像库存问题。

### 19.4 动态表名/列名的安全收口

`measure='table'` 必须把 `target_table`/`freshness_col` 拼进 SQL（标识符不能用占位符）。两道闸：

1. 正则 `[a-z][a-z0-9_]{0,63}`；
2. 用参数化查询查 `information_schema.COLUMNS`，要求「当前库 + 该表 + 该列 + 列类型 ∈ (datetime,timestamp,date)」计数为 1 才执行。

第二条同时挡住了配置写错和被人改成读别的表：配置值再离谱也读不出任何数据。实测两个探针（`sys_user.password` 与 `sys_user` + `password; DROP TABLE sys_user`）都返回 `measurable=false`、不告警、`sys_user` 7 行完好。

### 19.5 接口与前端

- `GET /admin/ingest/datasets` → 7 条健康快照（code/name/measure/slaHours/monitor/lastWriteAt/ageHours/stale/staleSince/writer/measurable）。只读；不提供写入接口——Python 无登录态（cron 里拿不到 token），继续按现有方式直写 `ingest_batch`/`ingest_raw`。
- 扫描周期做成配置：`spzx.ingest.scan-interval-ms`（默认 3600000）、`scan-initial-delay-ms`（默认 90000）。验证期用命令行临时降到 15s，未改默认值。
- 前端在**已有的任务进度看板**加「数据新鲜度」条，不新建页面/菜单：`monitor=1` 才给呼吸灯（绿=正常、红=过期），`monitor=0` 显示「契约预留 · 暂无自动写入方」灰标签，`measurable=false` 显示「配置指向的表/列不存在，无法判定」。两个请求改 `Promise.allSettled` 并行，新鲜度拉取失败时保留上一轮（慢变量不该闪空）。

### 19.6 验证记录

- 单测 `IngestFreshnessServiceTest` 8 条（SLA 边界、从未写入、SLA 缺省回落、一轮只告一次与恢复后再告、标识符白名单、文案含 SLA/最后写入/写入方、从未写入文案不假装有时间、列宽取满仍 ≤500）。`isStale` 改用 `Duration` 比较——`ChronoUnit.HOURS` 整除截断会把 30h01m 当 30h 放过，是单测逼出来的。
- 连跑 7 个测试类 25 tests 全绿；`mvn -q compile -pl spzx-manager` 通过；前端 `eslint` 干净、`npm run build` 9.06s 通过。
- 后端实跑（15s 节奏）观测完整生命周期：首轮 1 条告警 → 同轮内连跑多轮仍 1 条 → 放宽 SLA 后 `stale_since` 清空且日志「恢复新鲜」→ 改回 SLA 后新一轮再告 1 条（累计 2 条）。验证产生的告警行与状态已清理（`sync_alert` 0 行、两个 monitor 数据集 `stale_since/alerted_at` 归 NULL）。
- 前端 DOM 级验证通过：面板存在、副标题「纳入告警 2 / 登记 7」、7 行文案正确、`is-stale` 高亮恰好 1 行（sycm），原有 14 张任务卡与 2 张 Chrome 卡不受影响；控制台无新增报错。**截图仍拿不到**（in-app browser 无可见视口），颜色/间距未做像素级确认。
- 建表前后对账：`order_info` 43、`platform_product` 4679、`source_sku` 12786、`sycm_item_effect_history` 2999、`sync_alert` 0，全部未变；表注释无乱码（`ingest_dataset` 中文注释 HEX 正常）。

### 19.7 顺带发现（未改，属他人未完成的工作区）

`automation/sourcing/task-progress-config.json` 里 `taobao_cat_v2` 配了 `type: json_progress` 却没有 `fields`，后端每次读进度都 NPE 被 catch 成一行 warn，该卡片永远显示 0/0。修法是在配置里补 `fields`（`TaskProgressServiceImpl` 有未提交改动，暂不碰）。

## 20. 方案 C 落地：利润分析「解析1688链接」改为回读已采集行情（2026-09-29）

你选 C：能力（一次详情页访问拿 SKU+运费）已在 `automation/sourcing/collect_1688_full.py` 里存在并被验证过，缺的只是把结果接进后台口径。所以 Java 侧**不做抓取**，只把库里已有的采集结果按 offerId 回读——这与 D8「后端不接管采集、不 spawn 进程」和 AGENTS.md 的 CDP 端口分工一致。

### 20.1 offerId 到库行的映射（实测依据）

- `source_product.source_product_code` **就是**链接里的 offerId：2367 行 `.../offer/<id>.html` 的 code 与该 id 全等，且 `idx_offer_code` 已存在，等值查询走索引，不需要 `LIKE` 扫全表。
- 同一 offerId 有 **15 个重复 code**（重复铺货遗留）。取 `ORDER BY update_time DESC LIMIT 1`，即"最后一次采集的那行"。实测 `620752801635` 有两行（id 100 = 2.00/运费3.8/08-21 采集；id 2391 = 11.20/无运费/08-20），接口返回 id 100。
- `@TableLogic` 已自动过滤 `is_deleted`，无需显式条件。

### 20.2 口径：未采集与陈旧都不是异常

`GET /admin/product/sourceProduct/parse1688?offerId=` → `Source1688Vo{found, offerId, sourceProductId, title, url, sourcePrice, freightCost, collectedAt, collectedDaysAgo, stale, hint}`。

- `offerId` 只接受 6–20 位数字（`ServiceException` 给真实原因，不再被全局异常处理包成"您的网络有问题请稍后重试"）。
- 库里没有 → `found=false`、`code=200`、hint 说明"后台不抓 1688，请先在货源商品录入并等周六全量，或本页手工填"。**不用错误码**：未采集是正常状态，前端要按状态分支而不是接一个被拦截器 toast 掉的异常。
- 采集于 14 天前以上 → `stale=true`，hint 建议重跑 `collect_1688_full.py` 后核对。阈值来自该脚本的调度现实（每周六全量，最坏跨过两个周末）。

### 20.3 前端

- `Parse1688Product(offerId)` 只传 offerId（原来 `(url, offerId)` 两个都传，后端只可能用其一）；`Import1688Product` 0 引用，**删除**。
- 解析结果不再静默：输入框下方新增 provenance 行显示 hint（`is-stale` 用 `$neonOrange`）。`parsed1688Data` 此前只赋值从不渲染，等于把来源信息丢了。
- 运费回填条件从 `if (data.freightCost)` 改成 `!= null`——**包邮=0 是有效值**，旧写法会把 0 当成"没采到"跳过。
- 货源价从 `Number(data.sourcePrice) || 0` 改成只在非 null 时覆盖：未命中时不再把已填的值清零。

### 20.4 验证

- 后端四组实测：`724748321071`→found/id 664/¥27/¥6/3 天/不 stale；`620752801635`→取到 id 100/39 天→stale+重跑建议；`999999999999`→found=false+可执行提示；`1;DROP TABLE`、`12345`、空值→`code 500` 且 message 是真实原因。后端日志无 SQL 异常。
- 浏览器三条路径实测：新鲜（货源价输入框变 27.00，hint「采集于 3 天内，可直接采用」，无橙字）；陈旧（2.00/3.8 + 橙色 stale hint + 成功 toast 带"偏旧"后缀）；未采集（warning toast、hint 显示、**货源价保持 2.00 未被清零**）。
- 截图仍不可用（in-app browser 无可见视口），以上为 DOM 读数 + toast 文本。
- `mvn -q compile` 通过，7 个测试类 25 tests 全绿，前端 `eslint` 干净、`npm run build` 8.49s 通过。

顺带说明：验证期间看到 13 个 "Network Error" toast，来源是我自己把后台停掉重启时，仍开着的任务进度页每 30 秒轮询直连 8501 失败——`request.js` 只 toast 一次、页面保留上一轮数据，行为符合契约，不是新缺陷。

## 21. P1b 三件：跳过即告警、expense 店铺归属判定、旧账清理（2026-09-29）

### 21.1 跳过即告警：把静默窗口从"最快一小时"压到"当轮"

§19.2 证明了采集会静默失败，但 P1a 的新鲜度巡检是**事后判定**（`fixedDelay` 1 小时起步），而脚本在守卫那一刻就知道"我今天没跑成"。本轮补上这个信息差。

新增 `automation/sourcing/cron_alert.py`（纯 DB，无 Chrome）：`--key <任务标识> --msg <原因与影响> [--platform <code>]` → 写 `sync_alert(alert_type='cron_skipped', old_value=key, shop_id=?)`。

- 去重按 key 维度的未读提醒（`WHERE alert_type='cron_skipped' AND old_value=key AND status=0`）：运营读完之前不再重复插，读完之后下一次跳过才会再报。这一条同时解决了"归类v2 长跑期间 inventory_cron 每天跳一次=刷屏"。
- `shop_id` 只在任务确实属于某平台时写：`sycm_snapshot` → `default_shop_id(1)`=1；`collect_1688_full`/`fetch_freight`/`inventory_sync` 都是 1688 上游、跨平台复用 → **留 NULL**，与 `detect_alerts.py` 的货源侧口径一致（`shop_ref` 取不到就是 NULL，不伪造店铺）。
- 退出码恒为 0，且 DB 连接失败也只打日志：告警写不进去不能把 cron 链打挂。

插桩位置（8 个调用点，全部只在原有 `exit 0`/`exit $rc` 之前加一行）：`cron_sycm_snapshot.sh` 9222 不在线、target 为空、脚本异常退出（`rc=42` 风控 / `rc=1` 报错，语义读自 `sycm_item_snapshot.py:295`）；`cron_collect_full.sh`、`cron_freight.sh`、`inventory_cron.sh` 各 2 个守卫（Chrome 不在线 / 同类任务占用同一 Chrome）。

实测（9222、9223 都离线，直接跑四个脚本走真实分支）：4 条提醒落库、脚本 rc 全 0；再跑两个脚本 → 仍 4 行（去重生效）；`old_value=sycm_snapshot` 那行 `shop_id=1`，其余三行 NULL；中文按 utf8mb4 正常存储。验证产生的 4 行与 4 个 `/tmp` 日志已清掉，只留真实的那条 `ingest_stale`。

**为什么今天必须做这件事（新证据）**：本机 09:04 才重启，cron 守护进程 09:05 启动（`ps` 实测），而 sycm 快照排在每天 06:00——**今天这次不是 Chrome 守卫跳的，是机器没开**。这种失败任何脚本内告警都写不出来（进程根本没启动），只能靠后端事后判：`IngestFreshnessTask` 在 17:21 判出「已 59 小时未采集（SLA 30h）」，成为唯一兜底。两层各司其职，缺任一层都会瞎。

### 21.2 消费端补上：sync_alert 有接口、此前 0 个页面在用

`/admin/syncAlert/{list,read,readAll,count}` 四个接口在前端**没有任何调用点**（全仓 grep 无匹配），钉钉 webhook 又是空串（§19.6），意味着提醒写进去只有我这次能查到。所以在任务进度页加了一条「运维提醒」横条：`Promise.allSettled` 第三路拉未读 50 条、`ALERT_TYPE_DICT`（新增在 `constants/dict.js`，含 cron_skipped/ingest_stale/product_down/sku_down/price_change）出中文标签、单条已读 + 全部已读（走 `confirmAction`），新类型未知时回退显示原始 code 而不是空白。

浏览器实测：横条列出 5 条（4 定时任务跳过 + 1 数据陈旧），标签正确；点单条已读 → 5 条变 4 条、计数同步减；全部已读弹「确定把 4 条未读提醒全部标记已读？」→ 确认后横条整块消失；网络面板确认 `PUT /read/8`、`PUT /readAll` 均 200。

### 21.3 expense 店铺归属：结论是派生不出，不是没做

§5.2 把 `expense_*` 列为唯一挂着的派生例外。本轮按证据判定，**不加 `shop_id` 列**：

- 支付宝账单 11 列（交易时间/交易分类/对方账号/商品说明/收/支/金额/收付款方式/交易状态/交易订单号/商家订单号/备注）**没有店铺字段**，`AlipayBillCsvParser` 只取其中 5 列入库。
- 数据只有一个钱包：1908 行 / ¥92,092.11 / 2026-01-22~09-20 / channel 全是「支付宝」/ `source=1` 导入。最大金额桶是「转账红包」¥25,498.65（占 27.7%，56 笔），没有任何可判定信号；「服饰装扮」¥25,170.30 与「日用百货」¥7,496.96 里经营进货和个人消费混在一起。
- 现有 8 个标签（购物/饮食/交通/日用/娱乐/通讯/医疗/其他）是**个人消费**口径，且 `expense_order_tag` 关联 **0 条**——人工标注这条路没人走过。
- 店铺侧也没有承接方：`shop` 3 行全是 P0 合成的「X 默认店」，`cdp_port` 全 NULL，拼多多 `status=0`。给 1908 行加一个既派生不出、又没有第二个真实店铺可指向的列，就是 §19.1 拒绝过的那种装饰性 schema。

真正卡住"对账闭环"的是**收入侧为空**：`order_info` 43 行全在 2023-05~07，`profit_analysis_record` **0 行**，与 2026 的支出期零重叠——现在算"实际净利"只会得出"¥0 收入 − ¥9.2 万支出"这种正确答案但无意义的数。触发重做的条件写清楚：① 出现第二个真实店铺（`shop` 有真实 `outer_shop_id`/凭据）；② 2026 订单经 P1b/P2 采集落地。二者同时成立才谈店铺级成本。

本轮可落地的部分改成把**唯一真实维度**暴露出来：新增 `GET /admin/expense/stats/byCounterparty`（`COALESCE(counterparty,'未分类')` 分组，带笔数），前端对账单页加「按交易分类支出」横向条形图 + 口径说明一条（"账单不含店铺字段，因此只能按分类拆分，不能按店铺拆分"）。实测 22 个分类，前 8 类合计 ¥80,020.18（占总支出 86.9%），canvas 已绘制而非空态。这样"9.2 万花在哪"当场可答，而经营/个人的切分保持显式待办、不靠猜。

### 21.6 本轮验证记录

- 后端 `mvn compile` 通过；9 个纯单测类 **36 tests 全绿**（`EmailTest` 需 MySQL+Redis 在线且不在名单内，仍按 `-Dtest=` 单跑）。
- 前端 5 个改动文件 `eslint` 干净，`npm run build` 9.11s 通过。
- 对账单页实测：请求 `byCounterparty?days=30` 与切到 90 天后的 `days=90` 均 200，canvas 有实际绘制（非「暂无数据」空态）。
- 顺带证实 §20 遗留的一个疑问：切走后任务进度页**不再轮询**（在 /expenseStats 停留 66 秒，`taskProgress/overview` 的请求数没有增长，最后一个 reqid 停在离开看板那一刻）——P1a 的 `onDeactivated` 停表生效。
- 库面对账：`expense_order` 仍 1908 行 / ¥92,092.11（本轮只读不写），`sync_alert` 只留真实那条 `ingest_stale`（未读、`notified=0`），验证产生的 4 行 cron_skipped 与 4 个 `/tmp` 测试日志已清除，`vibe_images/` 已删。
- 截图通道依旧不可用，以上为 DOM/网络面板/canvas 像素采样读数；颜色与间距没有像素级验证。

### 21.7 补做：截图通道恢复可用，一眼看出一处 DOM 测不出的错

收尾时重测浏览器能力，`take_screenshot` 已经能出图（此前整轮都报 `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE`）。于是把 §20/§21 里"只能 DOM 读数"的两处界面真正看了一遍：

- **运维提醒横条**：粉边卡片、红 LED「待处理提醒 5 条」、4 条橙色「定时任务跳过」+ 1 条粉色「数据陈旧」、时间右对齐、单条「已读」与右上「全部标记已读」都在位；上方新鲜度条的过期项粉边与之呼应，布局无溢出。顺带发现长文案被省略号截断（`数据陈旧` 那条最长），补了 `:title="a.message"` 让悬停能读全文。
- **按交易分类图**：**截图抓到一处真 bug**，是前面所有 DOM/像素验证都发现不了的——y 轴与 series 都做过 `reverse()`，tooltip 的 formatter 却仍按 `rows[dataIndex]` 取行，于是柱子对得上、**笔数对不上**（悬停「保险」会显示「商业服务」的 20 笔）。改成 `rows[rows.length - 1 - dataIndex]` 后实测：悬停画布正中（第 6 根）弹出「保险: ¥45.97（4 笔）」，与接口 `days=30` 第 6 行 `保险=45.97/4` 完全一致。
- 结论层面要修正 §20.4/§21.6 那句"截图不可用"：**现在可用**，且这一轮证明它对图表类改动是必需的——canvas 里的语义错误只有看得见才抓得到。

### 21.4 旧账清理

- **`kw_provider.base_url` 回 https**：`GET https://ark.cn-beijing.volces.com/api/v3/models` 用库里那把 key 实测 **200 / 0.41s**（key 只读进变量、全程未打印，`/admin/kw/provider/list` 也不回显 apiKey），办公网对 ark 443 的拦截已解除 → id=3 已 UPDATE 成 https（WHERE 带旧值，可重复执行）。无 provider 缓存，改完即生效。TOS 主机 443 现在 TCP 能连上，但成片下载域名 `ark-content-generation-cn-beijing.tos-cn-beijing.volces.com` **TLS 仍被掐**：Client Hello 发出后 8 秒无 ServerHello 直到超时（2026-09-24 记录的 SNI 过滤症状未消失）。也就是"接口侧已解封、下载侧仍封"，真实签名 URL 下载需要换网或用 `--resolve` 指定可用 CDN IP 这条路依旧成立。
- **Ark Key 轮换**：仍需你亲手做（Key 不进对话）。「选词/视频生成」的 `api_key` 目前明文存在 `kw_provider.api_key`，这是当初为了让接口不泄露 key 到前端而留的库内明文，轮换后直接 UPDATE 那一行即可。
- **`vibe_images/`**：1 个 PNG（812K，`test_mug_flatlay_*`），全仓 0 引用、未 gitignore，已删除。
- **`feat/videogen` 合并**：分支领先 main **33 个 commit**，且 main 是 HEAD 的祖先——**已提交部分可以 fast-forward，无冲突成本**。但工作区还有 **50 个已改文件 + 56 个未跟踪文件（tracked 差异 +1068/−213）**，P0/P1a/方案 C/P1b 全部还没提交，此刻合并不会带走任何东西。建议顺序：先把本轮四件（cron 告警 / expense 分类 / @EnableAsync 修复 / P1a+C）按模块拆成几个 commit，再 FF 合并。提交需要你逐条授权，我没有动。

### 21.5 验证时挖出的一个真缺陷：dev 登录整条路是坏的

`POST /admin/system/index/wxLogin/create` 返回 `code 9999「您的网络有问题请稍后重试」`，后端日志是 `BeanNotOfRequiredTypeException: Bean named 'wxLoginServiceImpl' ... actually of type 'jdk.proxy3.$Proxy140'`。

根因：`@EnableAsync` 不带参数时按 **JDK 接口代理**处理带 `@Async` 的 bean，而 `WxLoginServiceImpl` 用具体类型自注入代理（`private WxLoginServiceImpl self`，为的是让 `saveTicketAsync` 真的异步）。懒加载把这个错推到首次调用才爆，所以只看启动日志发现不了。修法：`@EnableAsync(proxyTargetClass = true)`，与 Spring Boot 自身的 CGLIB 默认一致。

改后实测：`/create` 返回 200 带 ticket；账号密码登录（验证码从 Redis 读回，不猜不爆破）拿到新 token，前端整条守卫链路恢复。**这条链路此前对所有 dev 使用者都是坏的**，本轮能做完 UI 验证也全靠它修好。

## 22. P1b 跑批台账：让 ingest_batch 有真实写入方（2026-09-29）

### 22.1 为什么先做这个

P1a 建完三张表后实测：`ingest_batch` / `ingest_raw` 各 **0 行、0 个写入方**，只有 Java 读侧——正是 §19.1 拒绝过的那种装饰性结构。拼多多侧的写入方要等开店（§12.2），但 1688 侧四个 cron 任务今天就能记，且有一个当场可证的动机：看板上 4 个定时卡的"最近日志"读的是 `/tmp/*.log`，而 macOS 重启会清 /tmp。今天 09:04 重启后 `grade_quality` 卡的 lastLog 就是空的（实测 overview 返回 `lastLog=""`），跑批历史随之蒸发。

### 22.2 先修 P1a 自己的 DDL 错

`ingest_batch.platform_code` 写成了 `NOT NULL`，而 1688 上游采集（collect_1688_full / fetch_freight / detect_stock_change）对应的 `ingest_dataset.platform_code` 恰恰是 NULL（跨平台复用）。这条约束等于逼写入方编一个平台码。已 `ALTER ... MODIFY ... NULL`（表 0 行，零风险），CREATE 语句同步改掉。

### 22.3 台账契约

新增 `automation/sourcing/cron_batch.py`（纯 DB，退出码恒 0）：

- `begin --dataset X [--platform N] [--channel] [--biz-from/--biz-to]` → 插一条 `running`，stdout 打印 id；`end --id N --status success|partial|failed [--rows-*] [--error]` → 回填 `finished_at`。
- begin 失败输出空串，end 收到空 id 直接 no-op：台账写不进不能把 cron 打挂。
- begin 顺带把同数据集超过 12 小时仍 `running` 的行补成 `failed`（脚本被 kill、机器直接关机时的假"正在跑"）。实测：把一条行回拨 30 小时后再 begin，该行的 error 变成「未正常收尾：超过 12 小时仍是 running」。
- 四个 cron 包装器全部接上，**跳过分支也记一条 failed 批次**——跑批历史必须完整，否则"没跑"和"跑了没记录"分不开。`cron_sycm_snapshot.sh` 额外从本轮新增日志片段里取「入库 N 条」当行数：只扫本轮增量是必要的，实测同一份日志在"本轮无入库行"时旧写法会读到上一轮的 120 并记到本轮头上。
- 台账/告警的脚本输出改投 `/dev/null`：它们的落点是 MySQL，再灌进 `$LOG` 会把看板"最近日志"顶成包装器噪音（实测改后 lastLog 回到人类可读的那行跳过原因）。

### 22.4 两个新数据集，以及为什么不能用 measure=table

`source_freight`（周，SLA 192h）与 `source_stock_change`（日，SLA 48h）按 `measure=batch` 纳入监控。不能用事实表时间列的理由是实测出来的：

- `inventory_change_log` 是"有变化才写"的事件表，最后一行停在 **2026-08-13**（47 天前）。按它判新鲜 = 库存一稳定就一直告警，正是 §19.1 规则 2 排除的情形。
- `source_product.update_time` 同时被后台编辑写入，不能当采集心跳。

### 22.5 台账空白 ≠ 采集故障（bootstrap 规则）

新数据集纳入后第一轮扫描立刻报了 2 条「从未成功写入」——但那是**台账刚建立**，不是作业挂了（上周六 freight 确实跑过，只是那时还没有台账）。修法是在判定里区分：`measure=batch` 且该数据集**一条批次都没有**时不判过期、不告警，前端显示「跑批台账未建立 · 首轮成功后开始判定」并把呼吸灯给 `warning`（绿灯会在文案说"没法判"时谎报正常）。一旦有过批次（哪怕全 failed），恢复原语义：无成功批次即过期。

实测：把 `spzx.ingest.scan-interval-ms` 用环境变量压到 20s 跑两轮扫描，日志两次都是「source_freight / source_stock_change 跑批台账尚未建立，本轮不判过期」，`sync_alert` 保持 5 条不增、两行的 `stale_since` 保持 NULL。反向证据也在：之前台账里有 4 条纯 failed 批次时，这两个数据集确实各报了一条 `ingest_stale`——两个分支都跑过真数据。

### 22.6 看板与后端读路径

- `GET /admin/ingest/datasets` 的 `Health` 增加 `hasBatch` 与最近批次五元组（status/started/finished/rows/error），一条 `MAX(id) GROUP BY dataset` 联表查全部，不给每行发一条 SQL。
- 新鲜度条目下方多一行批次台账（success 绿 / partial 橙 / failed 粉 / running 青，悬停 title 给完整起止与错误）。
- `task-progress-config.json`：4 个定时卡补 `schedule` 文本（原先调度只塞在 tags 里，模板的时钟行从不渲染）、补 `sycm_snapshot` 卡（每天 06:00 喂着唯一 monitor=1 的淘宝数据集，看板上却没有卡）、给 `taobao_cat_v2` 补 `fields`。
- `TaskProgressServiceImpl.jsonIntOrLen` 增加 Map 分支：`shop_cat_v2_progress.json` 的 `failed` 是 **1023 键的 dict** 不是数组，此前读成 0。补 fields 后该卡从 0/0 变成实测的 已处理 1077 / 失败 1023（口径不含 skipped 1211，进度条是 done∶failed 比，不是全量完成率）。

### 22.7 验证与未验证

- 实跑四个包装器（9222/9223 全离线）：各写一条 `failed` 批次 + 一条 `cron_skipped` 提醒，rc 全 0；`/admin/ingest/datasets` 读出 4 个 monitor 数据集的批次字段；看板截图确认两行式布局、warning 灯与文案一致。
- `mvn compile` + 9 个纯单测类 36 tests 全绿；前端 eslint 无警告、`vite build` 通过。
- 收尾把验证产生的 5 条批次、4 条跳过提醒、2 条 bootstrap 假警与 4 个 /tmp 测试日志全部清掉：`ingest_batch` 回到 0 行，第一条真实记录留给今晚 05:00 与周六 03:00 的实际 cron；`sync_alert` 只剩那条真实的 sycm 过期未读告警。
- **未验证**：成功路径的批次行与真实行数（要 Chrome 在线跑一次真采集，不能凭猜写）；`--rows-*` 只有 sycm 有来源，其余三个任务的脚本不吐结构化计数，行数留 0 表示"未上报"，不是"采了 0 条"。

## 23. P1b 收尾：crontab 上最后一个无台账作业（2026-09-29）

### 23.1 盘点：6 行作业，2 行没装

`crontab -l` 实有 6 行调度，§22 装了其中 4 个 bash 包装器，剩两行直调 python：

- `task_stats.py`（每小时）核实为**只读**：读 task-progress-config.json 加两条 SELECT，结果 print 到
  `/tmp/cron_stats.log`，一行都不写库。没有"落库"可判的东西，给它建数据集纯属装饰，不做。顺带记录：
  它是看板 Java 侧 `TaskProgressServiceImpl` 的重复实现（两边读同一份 JSON），是否摘掉属调度台清理。
- `grade_quality.py`（每日 05:30）真写库：两条全表 `UPDATE ... CASE WHEN` 重算
  `source_product.quality_grade` 与 `source_factory.quality_grade`。

### 23.2 为什么分级作业必须有台账

`quality_grade` 不是展示字段，是 5 处读路径的筛选/排序条件：`SalesRankingMapper.xml` 里
`AND (sp.quality_grade IN ('A','B') OR EXISTS (... f.quality_grade IN ('A','B')))` 直接决定热销榜成员，
`ProductMapper.xml` 的 where + `ORDER BY CASE p.quality_grade`、`SourceFactoryServiceImpl` 排序、
`DashboardMapper`、`TaskProgressServiceImpl` 的厂家分级分布卡各读一处。作业静默跑挂 = 分级停在旧值，
而后台**没有任何地方看得出来**（看板上只有一张 `process_only` 卡显示文件 mtime）。

### 23.3 埋点位置：脚本内 import，而不是加包装器

crontab 那行是 `cd ... && python grade_quality.py >> /tmp/cron_grades.log 2>&1`，加 bash 包装器要改你的
crontab（机器状态，不动）。改为把 `cron_batch.py` 抽出 `begin_batch()/end_batch()` 纯函数、
`cron_alert.py` 抽出 `write_alert()`，CLI 的 begin/end 变薄壳——四个包装器的调用串逐字节不变，
两条路径共用同一份 SQL，不会出现"包装器改了、脚本内埋点没跟着改"。

### 23.4 channel 多一个取值 derived

`ingest_batch.channel` 此前注释只写了 api|browser|export（无 CHECK 约束，纯注释）。派生作业既不抓页面
也不读导出文件，硬塞三个里的任何一个都是谎报，故新增 `derived`，CREATE 与列注释同步。不加 CHECK：
每来一个新渠道都要 ALTER 一次，约束买不到东西。

### 23.5 台账记「覆盖行/出等级行」，不记「改动行」

幂等重算的 `cursor.rowcount` 第二次跑接近 0，报它等于报"这轮什么都没干"——和 §22.7 那个
"行数 0 是未上报还是采了 0 条"是同一类坑。实测口径：rows_total=6668（source_product 5369 +
source_factory 1299 全量覆盖），rows_ok=247（有等级：商品 A36/B66/C84 + 厂家 A12/B49）。

### 23.6 cron_skipped 与 cron_failed 是两件事，此前混成一个

告警原先只有一个类型 `cron_skipped`，把"守卫判定本轮不跑"（可能只是机器没开）和"脚本自己跑挂"
（是要修的 bug）报成同一个标签。新增 `cron_failed`（`alert_type varchar(20)` 容得下），四个包装器的
rc!=0 分支与 sycm 的 rc=42 风控分支一并改类型，`cron_alert.py` 的 `--type` 用 argparse choices 挡非法值，
前端 `ALERT_TYPE_DICT` 补一条红标签。

这个区分是被测出来的：第一次故障仿真时脚本没传类型，崩溃记成了 `cron_skipped`，看板上会显示
"定时任务跳过"——正是这种误导向让人不去修 bug。

### 23.7 验证

- 真跑 `grade_quality.py`（今天 05:30 那轮因 09:04 重启没跑成，这轮就是当天第一次真实重算）：
  `ingest_batch` id=10 `success / derived / total=6668 / ok=247`，**保留**为真实记录。
- 故障路径：把 `DB_CONFIG` 端口指到 3399 → 批次落 `failed`（error 带 `OperationalError: (2003, ...)`），
  同时写一条 `cron_failed` 提醒，异常照常往外抛（没被埋点吞掉，rc 非零）。
- 清理：仿真产生的 2 条 failed 批次与 3 条提醒全删。终态 `ingest_batch` 只剩 id=10 一条真实成功，
  `sync_alert` 只剩那条真实的 sycm 过期告警（已 65 小时无写入，SLA 30）。
- 自检脚本 `ingest_contract_p1a_verify.sql` 本身已过期，顺手校准并实跑：期望值 monitor=2 改 5；
  V3 从"只查 measure=table 的行"扩到"所有 monitor=1 的行"（batch 的 target_table 写错如今也会骗看板），
  实测 0 违例；F2 补 landed/failed 批次计数并用 IFNULL 归零（原先 LEFT JOIN 无匹配时 SUM 返回 NULL，
  读起来像查询坏了）。实况：`source_quality_grade` landed=1，其余三个 batch 数据集为 0，
  首条真实批次分别落在今晚 05:00/05:30 与周六 03:30。
- `bash -n` 四个包装器全过；`py_compile` 三个脚本全过；前端 eslint 干净。
- **未验证**：后端重启后的 `/admin/ingest/datasets` 读路径与看板渲染。本轮零 Java 改动、零布局改动，
  只是多一行数据集加一条字典标签，数据形状与 `source_freight` 同构，不值得为它整栈起 MySQL+Redis+8501。
- **未动**：你的 crontab 一行没改（这也是为什么埋点进脚本）；`task_stats.py` 的每小时调度保留原样。

## 24. detect_alerts 独立台账 + 一个会让告警静默消失的 shell bug（2026-09-30）

### 24.1 同一条 cron 里的第二段命令，此前共用第一段的 rc

`inventory_cron.sh` 每天 05:00 连跑两步：`detect_stock_change.py` 然后 `detect_alerts.py --type all`，
但 `rc=$?` 取的是第一步，第二步的退出码直接被丢掉——它跑挂时台账照样记 `success`。
`detect_alerts.py` 是 product_down / sku_down / price_change 三类提醒的**唯一生产者**（Java 侧只读不产），
停摆的后果是"货源下架了、抖店还在卖、后台一声不出"，正是这套台账要消灭的那类故障，
而它藏在刚建好的机制内部。实测 `detect_alerts` 崩溃会以 rc=1 退出（`get_conn()` 直抛），判得到，只是没人判。

修法：第二步独立 `begin/end` 一条批次（数据集 `source_alert_detect`，batch/SLA 30h/monitor=1，
target_table=`sync_alert`），rc!=0 时落 failed 批次 + 一条 `cron_failed` 提醒。纳入后 monitor=1 数据集 5→6。
行数口径写进 remark：这个数据集的"行数"= 本轮新增提醒条数，**0 是常态**（没检出问题），
故障信号看 status 不看行数——避免重演 §22.7 那个"0 是未上报还是零检出"的歧义。

跑之前先量了真跑一次的后果：`source_product.is_deleted=1` 0 行、全 SKU 下架商品 0 个、
绑定且下架的 SKU 0 个、绑定 SKU 总数仅 9 → 最多个位数提醒，不会刷爆。

### 24.2 `$变量` 紧跟全角字符会让整条告警消失（本轮实测挖出）

崩到故障分支后 `cron_alert` 一行都不落，但同样的命令单跑就成功。`bash -x` 抓到根因：
`--msg "...rc=$arc（product_down/..."` 里 `$arc` 后面直接跟全角括号，在 `LANG` 为空（cron 正是这个环境）
时 bash 把 `（` 的首字节 `0xEF` 当成变量名字符吃掉，留下 `0xBC 0x88` 这个非法 UTF-8 片段；
Python 用 surrogateescape 解出 argv，pymysql 编码时抛错，`write_alert` 把异常吞了（它必须吞——
告警不能拖垮作业）于是记录静默消失。

两处中招：一处在本轮新写的 `inventory_cron.sh`，另一处是 §21 就写进 `cron_sycm_snapshot.sh` 的
`rc=$rc（1=报错）`——那行需要"Chrome 在线且脚本跑挂"才会执行，所以潜伏了一整天没露头。
全量扫 `automation/**/*.sh`（排除 venv/node_modules/.git）命中就这 2 处，均已改成 `${arc}`/`${rc}`。

再加一层兜底：`cron_alert.write_alert` 与 `cron_batch.end_batch` 对 msg/error 做
`encode('utf-8','replace')`。理由同上——宁可消息里出现 `?`，也不能让一条记录整条丢掉。
防御测试：直接喂 `printf '\xbc'` 造出的非法字节 → 落库为「非法字节?后还有字」，记录在。

### 24.3 今晚的 cron 把 §22.7 那条"未验证"关掉了

机器 09-29 09:04 重启后 cron 守护恢复，09-30 凌晨三轮调度全部真实落账：

| 批次 | 数据集 | 时刻 | 行数 |
|---|---|---|---|
| id=13 | source_stock_change | 05:00:01→05:00:05 | 0（无变化，正常） |
| id=14 | source_quality_grade | 05:30:00 | 6668（本轮新装的埋点，第一次定时执行就成功） |
| id=15 | item_daily_sycm | 06:00:01→06:03:14 | 290（包装器按本轮日志切片解析出的真实行数） |

于是"成功路径的批次行与真实行数"从推测变成事实，包括 §22.6 那个按 `LINES_BEFORE` 切日志的取数写法。

### 24.4 后端读路径与看板实证（补 §23.7 的未验证）

起 8501 + vite 3001，`GET /admin/ingest/datasets` 六个 monitor 数据集全部映射正常：
`item_daily_sycm` lastWrite=09-30 06:03:13 / 批次 success 290 行；`source_quality_grade`
lastWrite=05:30 / 6668 行；`source_stock_change` 05:00；`source_alert_detect` 09:06；
`source_freight` `hasBatch=false` → 看板显示"跑批台账未建立 · 首轮成功后开始判定"（bootstrap 规则在真环境生效）。
09:15:21 首轮扫描日志两条：`item_daily_sycm 恢复新鲜（最后写入 2026-09-30T06:03:13）`、
`source_freight 跑批台账尚未建立，本轮不判过期`，`sync_alert` 未新增任何行。
看板截图确认：新鲜度面板 11 个数据集（纳入告警 6）、批次行与呼吸灯一致、
`cron_failed` 红标签正常渲染（探针提醒验证后已删）。

### 24.5 新发现，未修：过期告警不会随恢复而关闭

扫描恢复新鲜时只清 `ingest_dataset.stale_since`，**不动已经写出去的 `sync_alert` 行**。
截图当场就是活证据：同一面板上并存着「淘宝商品日效果快照 最后写入 09-30 06:03 · 批次 success 290 行」
和未读提醒「『淘宝商品日效果快照』采集已过期：已 59 小时没有成功采集…最后写入 2026-09-27 06:03」。
后者曾经是真的，现在永久是假的，只能靠人点"已读"。
根因是 `insertAlert` 没写数据集标识（`alert_type=ingest_stale`，`old_value` 存的是最后写入时刻，
`new_value` 存 SLA），Java 侧想自动关闭时也**认不出哪条告警属于哪个数据集**。
可选修法（待决，涉及 sync_alert 加列与状态语义）：
① 加 `dataset_code` 列 + 恢复时把该数据集未读的 ingest_stale 置为已处理；
② 加"已恢复"终态 status，保留可审计而不进未读列表；
③ 读路径按数据集名匹配消息前缀（不改表，但脆）。默认推荐 ②+① 一起做。

### 24.6 验证与清理

`bash -n` 四个包装器；`py_compile` 三个脚本；`ingest_contract_p1a_verify.sql` 期望值 monitor=5→6 后实跑
（V3 扩查 batch 行仍 0 违例）；前端 eslint 干净。清理：本轮仿真产生的 5 条 failed/running 批次与
5 条测试提醒（含 ui_probe / probe_bad / alert_detect）全删，终态 `ingest_batch` 5 行全为真实执行、
`sync_alert` 只剩 id=4 那条（即 §24.5 的证据），/tmp 探针脚本与两个服务日志、token 文件已删，
8501 与 3001 已停。

## 25. 过期告警自动关闭：dataset_code 外键 + 已恢复终态（2026-09-30，§24.5 的收口）

### 25.1 问题

§24.4 的截图就是活证据：同一面板上并存着「淘宝商品日效果快照 最后写入 09-30 06:03 · 批次 success 290 行」
和未读提醒「已 59 小时没有成功采集…最后写入 2026-09-27 06:03」。扫描恢复新鲜时只清
`ingest_dataset.stale_since`，不动已经写出去的 `sync_alert` 行，于是那条提醒永久挂着，
只能靠人点"已读"。根因是 `insertAlert` 没写数据集标识（`old_value` 存最后写入时刻、
`new_value` 存 SLA），Java 侧想关也**认不出哪条告警属于哪个数据集**。

### 25.2 落地（方案 ①+② 一起做）

- ① `sync_alert.dataset_code VARCHAR(32) NULL`（迁移 `sql/sync_alert_dataset_code.sql`），
  `insertAlert` 写入；只给契约类告警用，其他类型保持 NULL。
- ② `SyncAlert.STATUS_RESOLVED = 2`：条件自愈由系统关闭，行留在表里可审计，
  不再进未读列表。前端提醒条请求的是 `status: 0`，所以无需改前端就能消失；
  整条提醒带 `v-if="alerts.length"`，清空后连 error 呼吸灯一起隐藏，不会留下"红灯但没内容"。
- 关闭时同时置 `notified=1`。`SyncAlertNotifyTask` 只按 `notified` 过滤、不看 status，
  现在 webhook 没配 → 这条历史欠账会等你哪天配上钉钉就一次性推出去，推的是一句已经假了的"59 小时没采集"。
  推一条自愈的假警报比不推更糟。
- 不加索引：`sync_alert` 是几百行量级的小表，每小时按 `(alert_type, dataset_code, status)`
  更新个位数行；表长到万行再回来加。

### 25.3 不只关在"过期→新鲜"的转换瞬间

初版把关闭挂在 `stale_since != null` 那个分支里，实测立刻漏：本机 `item_daily_sycm` 的
`stale_since` 早在 09:15 那轮就被清了（那时还没有关闭逻辑），转换已经发生完毕，
按"只认转换"的写法这条历史行永远不会被关。改成**只要判到新鲜就扫一遍**——
UPDATE 只匹配 `status=0`，无匹配即空操作，每轮跑是幂等的。这样应用停机期间发生的转换也能补上，
而应用停着不动正是这台机器的常态。

### 25.4 历史行回填

`message` 由 `insertAlert` 固定生成，开头是「<数据集名>」，所以回填只能靠名称映射：
`UPDATE ... JOIN ingest_dataset ON message LIKE CONCAT('「', d.name, '」%')`。
不把中文名写死在脚本里，否则哪天改数据集名就回填不上。迁移自带的自检
`unresolved_ingest_stale` 实测 = 0。

### 25.5 验证

- 迁移执行后 `id=4` 拿到 `dataset_code=item_daily_sycm`，自检 0 行未回填。
- 临时把扫描参数压到 initial-delay 4s / interval 20s（只改命令行，不动 yml）实跑：
  日志 `ingest 数据集 item_daily_sycm 已新鲜，自动关闭 1 条过期告警`，
  库里该行变 `status=2 / notified=1`；随后 3 轮扫描"自动关闭"日志计数仍为 1（幂等成立），
  调度任务错误 0 次；`sync_alert` status 分布只剩 `2=1`，未读列表为空。
- `mvn test`（8 个纯单测类）32 tests 全绿 BUILD SUCCESS；`mvn compile` 干净。
- **未做**：没为关闭逻辑补单测。它是 `sync_alert` 上的一条 UPDATE，纯单测要么 mock mapper
  只断言"我调用了自己"，要么得拉 Spring 上下文（`EmailTest` 那类，本机环境不全必挂），
  两条都不值；上面已经有真环境的行为证据。

### 25.6 两个自己造的坑（记下来免得再踩）

- 改了 `spzx-model` 的实体却不 `mvn install -pl spzx-model`，`spring-boot:run` 会用 `~/.m2`
  里的旧 jar，运行期报 `NoSuchFieldError: SyncAlert.STATUS_RESOLVED`——编译期完全看不出来。
  AGENTS.md 第一行构建命令就写着这个顺序，是我跳过了它。
- `-Dspring-boot.run.arguments` 的分隔是**空格**不是逗号：写成 `--a=4000,--b=20000` 会让
  第一个属性拿到整串值，`@Scheduled` 的 `initialDelayString` 解析失败直接把应用启动顶掉。

### 25.7 本轮 git

后端 7 笔（`feat(platform)` P0 / `feat(ingest)` 契约与新鲜度 / `feat(cron)` 台账与告警 /
`feat(expense)` byCounterparty / `feat(product)` parse1688 / `fix(config)` 路径 / `docs(spec)`），
前端 3 笔（看板新鲜度与运维提醒 / 对账分类图 / parse1688 调用点）。**未 push**。
你自己的在途改动（novel / kw / videogen / sysdict / 关账 / detect_alerts.py / probe_*.py /
AGENTS.md 等）一笔没动、一笔没带。§25 这份修复（`sync_alert_dataset_code.sql` + 实体 + 服务）
按你的指示先做完未提交。

---

## 26. 转向业务功能：店铺维度、费用自动打标、首页换真数据源、商品运营台（2026-09-30）

### 26.0 为什么转向

你说"钉钉就不需要了，把一个正常的电商运营管理系统的功能做好就可以"。§22-§25 那条线（跑批台账、
告警闭环）到此收口，`spzx.alert.dingtalk-webhook` 不再作为待办。这一节起，做的是后台本身的功能缺口。

先做了缺口盘点，不猜。结论：**货源侧（1688）已经结实，平台经营侧基本是空壳**。

| 环节 | 库里真实数据 | 有无页面 | 判定 |
|---|---|---|---|
| 1688 货源 | 5369 商品 / 12380 SKU / 1299 厂家 / 质量分级 / 运费 | ✅ | 完整 |
| 平台在售商品 | 4679（淘宝 3110 / 抖店 1569），有定价运费；**表里没有上下架状态、没有库存、没有销量列** | ✅ | 字段残缺 |
| 平台 SKU | `platform_sku` **14 行**，`sku_bind_relation` 9 条 | ✅ | 几乎没采 |
| 平台订单 | `order_info` **43 行，全是 2023-06 联调数据**，真实成交 0 单入库 | ✅ | 空壳 |
| 商品经营效果 | 生意参谋快照 290~442 商品/次（09-30 那份：UV 14966、成交 0） | ⚠️ 只有 salesRanking 一个入口 | 数据富、UI 穷 |
| 费用对账 | 1908 笔 / 9.2 万 / 2026-01~09，**打标 0 笔** | ✅ 三页 | 闭环断了 |
| 店铺 | `shop` 3 行，`order_info`/`refund_*` 的 shop_id 100% 回填 | ❌ 无维护页、全站无店铺筛选 | 半成品 |
| 后端全 CRUD、前端零入口 | 规格 / 单位 / 品牌 / 类目 / 人力成本 / 推广计划 / Farm单 / 商品链接 / 订单货源 | ❌ | 建了没人用 |

四个当场指认的缺陷：首页 KPI 用 `COUNT(*)/SUM(total_amount) FROM order_info` 算"订单数/销售额"
（读到的是 2023 年那 43 条）；`expense_order_tag` 0 行导致「标签管理」「按标签统计」两页全空；
`RefundReportPageDto` 没有 `platformType` 字段，退款报表页的平台 Tab 一直在传但被丢弃（切 Tab 等于没筛）；
`orderList.vue` 的 `searchForm` 声明了 platformType/orderStatus/orderNo 却没有任何输入控件，是死状态。

你选了"四块都做"，顺序 D→B→A→C。

### 26.1 D 店铺维度

`PlatformRegistryService.listShops` 是采集用的只读注册表，会抹掉 `credential_ref` 与 `cdp_port`。
维护页必须看到并编辑这两个字段，所以**新开一条写入路径**而不是把只读接口改成"既隐藏又展示"：

- `ShopService`（校验 / 同名冲突 / 默认店互斥 / 引用计数）+ `ShopController` `/admin/shop/{list,usage,POST,PUT,DELETE}`
- 默认店按平台唯一：设新默认时清同平台其它 `is_default`，否则 `defaultShopId` 在两店之间摇摆，采集落到哪个店不确定
- 停用店不得为默认（`shop` 表里 id=3 拼多多默认店原本就是 `is_default=1 + status=0` 的非法组合，保留原值未改）
- 删除保护：被 `platform_product`/`order_info`/`refund_import_order`/`sync_alert` 引用即拒绝（店 1 实测 3373 条）
- 编辑走 `ShopService.mergeEditable` 纯函数：文本 `null` 表示"不改"、`""` 表示"清空"，所以只切启停的 PATCH
  不会把凭据引用和 CDP 端口抹掉（这条最容易写错，单测 `ShopFieldMergeTest` 5 例锁住）
- 前端 `views/mall/shopManage.vue`（菜单 id=74）+ 复用组件 `components/ShopSelect/index.vue`
- **shop_id 覆盖范围实测**：`order_info`、`platform_product`、`refund_analysis_*`、`refund_import_order`、
  `sync_alert`、`ingest_batch` 有；`expense_order`、`source_product`、`source_sku` **没有** →
  费用不能按店分，只在有列的域加筛选（商品 / 订单 / 售后三处）

### 26.2 B 费用自动打标

`expense_order_tag` 是 `(order_id, tag_id)` 联合主键，一笔可多标；标签筛选、`/stats/byTag`、
`assembleVos` 早就写好了，**缺的从来不是管道，是没人往里写**。

- 新表 `expense_tag_rule(tag_id, match_field, match_type, keyword, min/max_amount, status)`，
  种子 13 条把支付宝「交易分类」逐项映射到已有 8 个标签（按标签名反查 id，不写死）
- `ExpenseTagRuleMatcher` 纯函数（eq 忽略首尾空格与大小写、like 子串不区分大小写、金额闭区间、
  未知字段不命中而不抛异常）→ 单测 10 例
- `POST /admin/expense/rule/autoTag?dryRun=&onlyUntagged=`：**默认 dryRun=true 先给命中预览**，
  确认了再实写；只新增关联从不删除，人工打过/改过的不会被跑批抹掉；已关账月份跳过
- 预览结果带 `uncovered`（还没被任何规则覆盖的分类 + 笔数 + 金额 + 一键"加规则"），
  不替你做经营口径的分类决定
- `POST /admin/expense/order/batchTag {ids, tagIds, replace}`：人工多选批量补打，replace 才清旧标
- 实跑结果：**1908 笔中 927 笔打上标签**（购物 387 / 饮食 287 / 交通 227 / 娱乐 12 / 通讯 10 / 医疗 4），
  `/stats/byTag` 从空数组变成有数；重跑一次 scanned 981 / matched 0 / created 0（幂等 + onlyUntagged 生效）
- 未覆盖的 981 笔集中在：商业服务 533、其他 343、**转账红包 56 笔 ¥25498.65**、保险 30、教育培训 4。
  这几类是经营支出，现有 8 个个人消费标签装不下 —— 要新增"推广费用/采购进货/人情往来"这类标签的话，
  在页面上加规则即可，我没有替你建 taxonomy

### 26.3 A 首页驾驶舱

`DashboardMapper` 的 `countOrders`/`sumOrderAmount`/`selectOrderTrend` 全部来自 `order_info`（2023 假数据），
换成唯一真实的平台经营源 —— 生意参谋商品效果快照：

- KPI 六张卡：近7日成交 ¥0 / 近7日访客 14,966（+14,832，+11068.7%）/ 本月支出 ¥4,505（99 笔）/
  未读提醒 0 / 平台商品 4,679 / 货源商品 5,369
- `/orderTrend` → `/effectTrend`：**按 snapshot_time 而不是按天分组**，同一天跑两次会被日期分组加成两倍 GMV；
  每个点是"那次快照覆盖的近 7 日汇总"，点与点之间是重叠窗口，不是当日新增
- `DashboardServiceImpl.buildKpi` / `toChronological` 是纯函数（单测 7 例）。关键一条：
  **没有快照时经营指标返回 null 让前端显示"暂无"，而不是 0** —— 显示 0 会被读成"今天一单没出"
- 界面必须挂口径说明（"生意参谋近 7 日滚动汇总，不是当日流水" + 快照时间 + 覆盖商品数），
  否则只是换了个方式骗人
- `order_info` 那 43 条种子数据我没动，`orderList` 页保留

顺带发现（未处理，供你判断）：09-22~09-28 那份快照 UV 14966、成交 0，而 09-19~09-25 只有 UV 134。
`visitors`/`page_views`/`extra_json` 三者自洽，不是采集解析错，是真实的一百倍流量跳变 + 零成交。
这正好是商品运营台"有流量没成交"筛出来的 84 个商品。

### 26.4 C 商品运营台

`/admin/mall/itemOps/{page,facetCounts}`：`platform_product` × 最新效果快照 × 绑定货源成本 × `fee_benchmark` 费率。
只读页，改价/绑货源仍在平台商品页做（带 `platformType+keyword` 跳过去，`mallProduct` 现在会读这两个 query）。

- 毛利口径：`定价 - 货源最低进价 - 定价×(技术服务费+支付费)/100`，进价取已绑定货源里在售 SKU 的最低价，
  费率取该平台各类目均值（当前 5 个类目都是 4.00% + 0.60%，均值即精确值）
- 七个筛选项一次 SQL 算齐数量（`facetCounts`），实测与分页 total 逐项一致：
  全部 4679 / 有流量没成交 84 / 毛利为负 18 / 库存告急 2 / 未定价 1115 / 没绑货源 728 / 没效果数据 4364
- 抖店 1569 个商品完全没有效果数据（sycm 只覆盖淘宝），淘宝也只有 315 个对得上 →
  效果列显示"未采"而不是 0

### 26.5 这一节里踩到的六个坑（都值得留字）

1. **MyBatis-Plus 的 count 优化器会剥掉 join 和 select 列表**。`HAVING effectAt IS NULL` 被优化成
   `SELECT COUNT(*) AS total FROM platform_product p HAVING effectAt IS NULL` → Unknown column。
   改法：筛选项作用在派生表的外层 `WHERE`，并 `page.setOptimizeCountSql(false)`。
2. **COLLATE 加在哪一侧不是风格问题，是 24 倍性能差**。四张表排序规则三样（unicode_ci / 0900_ai_ci / general_ci）。
   把 `e.item_id` 转成 unicode_ci 会让物化临时表的自动索引失效，4679×442 退化成逐行全扫，实测 **1.14s**；
   改成把被扫描侧 `p.code` 转成 0900_ai_ci，**0.047s**（整页 2.3s → 0.11s）。
3. **`pricing = 0` 不是"卖不过成本"，是"还没定价"**。库里 1115 个商品定价为 0，不排除的话
   「毛利为负」会报 1118 条、其中 1100 条是假亏本。现在 margin 在 pricing 为 NULL/0 时判不可算，
   另开「未定价」档，真亏本 18 条。
4. **ProTable 自己占了 `#title` 作为卡片标题插槽**。我给"标题"列写 `tdSlot: 'title'`，单元格模板被当成
   卡片标题渲染，`row` 是 undefined → 整页白屏 + `Cannot read properties of undefined (reading 'title')`。
   截图上看是"数据错位"（定价显示 149、接口返回 156），逐格比对 DOM 才定位到插槽冲突。
5. **`batchTag` 传不存在的订单号会插出孤儿关联**。第一次测试用 `ids:[0]` 试出库里多了一条 `order_id=0`。
   改成以 `selectBatchIds` 查出来的行为准生成关联，并补了回归用例。
6. **新表默认排序规则会跟邻居不一致**。`expense_tag_rule` 建表时不写 COLLATE 就继承服务器默认
   `utf8mb4_0900_ai_ci`，而整个 expense 域是 `utf8mb4_general_ci`，自检 SQL 当场报 Illegal mix of collations。
   DDL 已显式 `COLLATE = utf8mb4_general_ci`，线上表 `ALTER ... CONVERT TO` 对齐。

### 26.6 验证

- `mvn test`（13 个纯单测类）**61 tests，BUILD SUCCESS**；`mvn compile -pl spzx-manager` rc=0
- 后端接口实测（真 token、真库）：店铺 CRUD 11 例（含 5 条校验拒绝、默认店互斥、只读注册表抹字段 vs
  维护页露字段、删除保护 3373 条）、shopId 筛选 5 例（含跨店应为 0）、自动打标（预览 927/实写 927/重跑 0）、
  batchTag 6 例（孤儿 id / 追加 / 重复追加 / 替换 / 关账拒绝 / 清理）、itemOps 七档 + 乱写 facet + 平台店铺关键词组合
- 前端 `npx eslint` 全部改动文件 0 error（mallProduct 6 条 unused-var 警告是改造前就有的死代码）
- 浏览器实测（登录态 + 截图 + DOM 逐格比对）：首页六卡与口径说明、商品运营台（筛选项数量与接口逐项一致）、
  店铺管理（拼多多平台名修复后）、标签管理（预览命中面板含 9 条未覆盖分类）、账单记录（标签列已落标 +
  批量打标签对话框真实写入 2 笔后回滚）、平台订单（新筛选栏 + 店铺列）
- 测试数据全部清理：探针店铺 4/5 已删、店 3 的 `is_default` 还原为 1、`expense_order_tag` 回到 927 行、
  验证用的 2 条「日用」标签已删、无孤儿关联

### 26.7 仍然弱的地方（不粉饰）

- 平台订单真实入库没做 —— 这是唯一能补上真实 GMV / 退款率的路，需要你的浏览器在线 + 抖店/淘宝采集，单独排期
- `platform_sku` 14 行、SKU 级绑定 9 条：库存/断货/变价提醒在平台侧的作用域只有这 9 个 SKU，
  所以"库存告急"筛出来只有 2 条不是好消息，是覆盖面问题
- 商品运营台只覆盖淘宝 315/3110 个商品；另有 127 个 `item_id` 在 `platform_product` 里查无此品（已下架或没采全）
- `platform_product` 表**没有上下架状态列**，所以这一页无法回答"这个商品还在不在架"
- 费用打标覆盖率 48.6%（927/1908），剩下 981 笔集中在经营支出，要新标签才能装
- §25 那句"按你的指示先做完未提交"已过期：§25 与本轮之前的改动都已提交并 ff 到 main（`41df49e`），
  **本轮 §26 的改动按你的习惯先不提交，等你说提交**。前端远程是 Gitee，同样未推。

---

## 27. 淘宝付费推广日报导入骨架（2026-09-30，真实导出文件到手前先立骨架）

用户开了「关键词推广标准计划」与「人群推广标准计划」，要把每日数据导进来分析。
真实导出文件晚上才有，所以这一节的判断标准是：**在没见过列名的前提下，搭一个不会因为列名不对就丢数据、
也不需要改代码重发版的骨架。**

### 27.1 现状盘点（先查再动手）

- `ingest_dataset` id=7 早就登记了 `promo_cost`「推广花费」契约：`target_table=promo_cost_daily`、
  `required=campaign_id,stat_date`、`sla=30h`、`monitor=0`、remark「目标表尚未建」。**表没建、没有写入方。**
- `sycm_sy_ztkb` / `sycm_sy_llkb`：一天一行的**店铺级**宽表，字段里已经有 `keyword_fee`（关键词推广花费）、
  `exact_crowd_fee`（精准人群推广花费）、`full_site_fee`、`intelli_scence_fee`、`taobao_customer_commison`。
  但全仓 **0 引用 0 写入**（Java 无实体无 mapper、Python 不写、前端不读），是上一套系统的遗骸。
- `keyword_plan_product` / `keyword_plan_product_word` / `keyword_plan_crowd` / `oper_promotion_plan`：
  计划**配置**侧（单元、关键词出价、人群溢价/规模），同样 0 引用；AI 选词 spec 已写明"不复用现有空表 keyword_plan_*"。
- 判断：店铺级日汇总答不了"哪个词/哪个人群在烧钱不出单"，所以按契约新建 campaign/item 两级事实表，
  **不去改那批遗骸**（改一张没人用也没人验证过的表，风险大于收益）。

### 27.2 三条设计约束（都源于"列名还不知道"）

1. **列名映射是数据不是代码**：`promo_import_map(report_level, source_column → target_column)`，
   解析器 `PromoReportCsvParser` 里一个中文列名都不写。猜错的代价从"改代码重新发版"降成"改一行数据"。
   预置 49 条常见列名，全部 `verified=0`，等真实文件核对。
2. **未映射的列必须报出来，绝不静默丢**：预览结果返回 `headers / matched / unmapped / unknownTargets /
   missingRequired`。第一次拿到真实文件时，靠 `unmapped` 补映射即可。
3. **整行原始值留在 `raw_json`**：映射以后怎么改，历史行都能重放，不用重新导出。

另外两条口径决定：
- 百分比按报表原样的百分数存（`ctr_percent=12.34` 表示 12.34%），**不在导入阶段猜**导出给的是
  `12.34%` 还是 `0.1234`；配合 `raw_json` 事后能判断也能重算。
- 所有指标列可空。空=报表没给，0=报表给了 0，两者不能混（`-`、`--`、`/`、`暂无`、`N/A` 一律归 null）。

### 27.3 落地的东西

| 对象 | 说明 |
|---|---|
| `promo_cost_daily` | 计划粒度日报，唯一键 `(shop_id, plan_type, campaign_id, stat_date)` |
| `promo_cost_item_daily` | 明细粒度（关键词/人群/创意/宝贝/地域），唯一键含 `dimension+entity_key` |
| `promo_import_map` | 列名映射，49 条预置，`verified` 标记是否已用真实文件核对 |
| `CsvText` | 从 `AlipayBillCsvParser` 提出的共享件：utf-8/gb18030/BOM 探测 + RFC4180 切分 |
| `PromoReportCsvParser` | 纯函数：表头定位、列映射体检、值归一化（¥/千分位/万/亿/%/多格式日期） |
| `PromoRowConverter` | 纯函数：按 DDL 精度收窄，单行字段坏只报这一行，不整批回滚 |
| `PromoCostService` | preview/commit 同一入口（`dryRun`），自然键 upsert，按批次号整批回滚 |
| `/admin/promo/*` | mapping CRUD + `import/preview` + `import/commit` + `import/batch/{batch}` |

契约同步更新：`promo_cost` 的 `natural_key_cols` 改成 `shop_id,plan_type,campaign_id,stat_date`
（原登记的三列不够——同一天的同一计划在关键词报表和人群报表里会各出一行），
并新增 `promo_cost_detail` 数据集。两者 `monitor` 先留 0：**首次成功导入前开监控必然产生一条假过期告警**（§24 的 bootstrap 规则）。

### 27.4 端到端验证（造了一份 gb18030、带标题块、含未映射列的假报表）

- 表头自动定位到第 3 行，标题块跳过；`"¥1,234.50"` → 1234.50、`2.17%` → 2.17、`-` → NULL
- `unmapped` 如实报出 `['平均展现排名','总收藏加购数']`，没有静默丢
- commit 3 行 → 重导同一份 `inserted=0 / overwritten=3`（upsert 生效，MySQL 9.6 接受 `AS new` 行别名语法）
- 按批次回滚返回 3，表清空
- 映射校验：非法目标字段列出白名单、同列名重复拒绝
- 明细层 join 验证：`item_id → platform_product.code` 命中真实商品（88 / 2924），
  关键词花费 + 商品定价同表可查 —— 这是"把推广费摊到商品算真实 ROI"的桥，通了
- `mvn test` 全量 **93 tests BUILD SUCCESS**（新增 `PromoReportCsvParserTest` 25 例、`CsvTextTest` 8 例）
- 探针数据与临时文件已清理，两张事实表留空，49 条映射留着待核对

### 27.5 测试暴露的一个真设计缺口

第一版明细表只有一套 `entity_*` 标识。造关键词维度的假报表一跑就露馅：
真实报表的一行是 **(关键词, 该词投在哪个宝贝)** 的配对，`关键词` 和 `宝贝ID` 挤进同一个 entity 字段后，
要么关键词文本被宝贝 id 顶掉，要么 `dimension` 认成 `other` —— 而宝贝 id 正是后面 join 商品的唯一桥梁。
补了独立的 `item_id` / `item_name` 两列，`关键词→entity_keyword`、`宝贝ID→item_id` 各归各位，
并把「明细必须至少映射一个实体列」的校验从"必须叫 entity_name"改成"六个候选列任一命中"。

### 27.6 还没做

- 前端上传/映射页（今晚把 CSV 给我或给路径，我用接口导；页面等你确认列名后再做更省事）
- 推广费进商品维度后，把 `itemOps` 的毛利改成**扣掉推广费**的真实毛利
- 开放平台 API 路线未探（个人店大概率没有阿里妈妈报表接口权限，未核实）
- 成交归因窗口（累计成交 vs 当天成交）在真实文件里怎么体现，等文件到了再定列
