# 1688 货源库存全量监控（建档 + 分级刷新 + 失效告警 + 同步核验）设计

日期：2026-10-18
状态：已与 owner 逐项确认，待实施
前置：2026-10-16 低库存规格页（见 `2026-10-16-low-stock-spec-page-design.md`）、ISV 全量库存同步（`isv_stock_sync.py`）、ISV 规格匹配（`2026-10-14-isv-sku-match-design.md`）

## 0. 一句话

把「在卖的每一件商品，其 1688 货源没货/失效都能当天知道」做成闭环：全量建档 → 分级刷新库存 → 失效告警+页面标记（人工下架）→ ISV 同步提频并持续核验「没货→淘宝 0」真的生效。

## 1. 背景与问题

owner 原话诉求：「每天都要更新库存，避免 1688 货源库存没了，我这边还在卖，这样就会造成无法发货」。

现状四类缺口（2026-10-18 探查确认）：

1. **货源整个失效时同步推不动**：`isv_stock_sync.py` 走 ISV 控制台「批量同步库存」，源头商品下架/失效后无库存可推，淘宝挂着旧库存继续卖——最危险。
2. **一天一次同步不够快**：05:30 一轮，白天卖空要等次日才发现。
3. **同步可靠性无证据**：报告只记页数（`stock_sync_report.json`），不知道 0 库存是否真推成了淘宝 0。
4. **本地库存数字太旧**：`detect_stock_change.py` 851 池每天只轮 60 个（14 天一轮），低库存页对大部分商品显示的是十几天前的数字。

## 2. 决策记录（owner 已拍板）

| # | 决策 |
|---|------|
| D1 | 处理动作分级：0 库存（商品还活着）→ 依赖 ISV 同步自动推 0；商品整个失效 → 告警 + 页面标记，**人工**决定下架（不做自动下架/自动改淘宝库存） |
| D2 | 刷新策略分级：危险商品每天刷，充足的 3-7 天轮一遍（非全量每晚刷） |
| D3 | 实现路径选方案 A：复用现有管线、扩围建档（否决另起快照表/只做动作层） |
| D4 | 周六 03:00 `collect_1688_full` 全量采集**退役**（被分级刷新取代）；运费不打紧，后续统一按 **8 元定值** 计算 |
| D5 | T1 危险池阈值默认 **100**（低于 100 件每天刷新），CLI 可调 |
| D6 | 建档会向选品库新增 ~3000-3400 个 `data_source=2` 货源（总数 5847 → ~9000），看板统计数字会变，owner 知情 |

## 3. 现状盘点（实施依赖的关键事实）

- **`taobao_offer_map`**（4190 行）：taobao_item_id ↔ offer_id 绑定宇宙 = ISV 控制台 4203 个已关联货源；`source_product_id` 仅 664 行（15.8%）有值，84.2% NULL。NULL = 货源在 `source_product` 无行 **或** URL 匹配没对上（`source_product` 5847 行中仅 2367 行 URL 含 offer id）。
- **采集能力现成**：`detect_stock_change.py` 拦截详情页 `mtop.1688.wosc.queryofferskuselectormodel` 的 `skuInfoMap[].canBookCount` → 写 `source_sku.stock/price` + `inventory_change_log`；GONE_HINTS 识别「商品已下架」。`collect_1688_full.py` 同 API 全量采集。
- **`source_product`**：无库存字段、无失效状态字段；有 `data_source`（1=搜索候选 2=ISV已铺货）、`platform_type`（1淘宝）、`source_product_url`（关联锚点）。
- **`source_sku`**（17,516 行，脚本维护，无 Java 实体）：sku_key/sku_id/spec_id/stock/price/status(1在售 0下架)。
- **推送侧**：`isv_stock_sync.py`（05:30，~17min，100 条/页×43 页）只记页数；`sync_douyin_stock.py` 读 `source_sku.stock` 推抖店（自动受益于刷新，无需改造）。
- **告警侧**：`detect_alerts.py` 每日写 `sync_alert`（顶栏铃铛，owner 明确不推 IM）；`sku_down` 规则依赖抖音侧 `sku_bind_relation`，淘宝无对应物。
- **低库存页**：`source_sku JOIN source_product` + `EXISTS taobao_offer_map`，处理按钮纯留痕（`low_stock_handle`）。
- **调度撞车约束**：9222 现有 05:00 inventory_cron（60个+告警）、05:30 stock-sync、06:00 sycm（窗口）、22:00 alimama；周六 03:00 collect_full（将退役）。白天归类 v2/品牌批处理可能随时占 9222（新任务必须带守卫）。
- **crontab 不可程序化写入**（2026-10-07 实测 CLI 装载挂死）→ 调度变更只能：新增走 LaunchAgent，已有 crontab 行**脚本内容退役**（行物理保留）。

## 4. 总体数据流

```
[P1] taobao_offer_map(4190) --补映射+建档--> source_product/source_sku 全量有档（含死链 source_status=0）
        |
[P2] 03:00 分级刷新(T1每日/T2七分之一/T3周检) --> source_sku.stock 每日新鲜 + source_status 保鲜
        |
[P3] detect_alerts 新规则 source_dead --> sync_alert 顶栏告警 + 低库存页「货源失效」筛选/徽标 --> 人工下架（现有标记按钮）
        |
[P4] 05:30/12:30/19:30 ISV 批量同步（1688库存→淘宝SKU） + 0库存行级核验(stock_sync_check) --> 超卖窗口压到半天量级
```

## 5. 分期设计

### P1 加列 + 补映射 + 全量建档（一次性，采集 2-4 晚）

新脚本 `automation/sourcing/backfill_offer_archive.py`，三步：

0. **前置加列**：`ALTER TABLE source_product ADD COLUMN source_status TINYINT NULL`（1=正常 0=失效 NULL=未检测；迁移 SQL 落 `spzx-manager/src/main/resources/sql/`）。加列后 Python 侧建档即可直接写失效标记（后端实体/VO 到 P3 消费时才动，多余 DB 列对 MyBatis-Plus 实体无害）。
1. **补映射（零采集）**：正则 `offer/(\d+)\.html` 扫全部 `source_product_url` 建 offer_id→source_product_id 映射，UPDATE `taobao_offer_map` 能补尽补（避免重复建档）。报告补回数量。
2. **建档（采集）**：仍无档的 offer（估 ~3000-3400）逐个开 `detail.1688.com/offer/{id}.html`（CDP 9222，复用 detect_stock_change 的响应拦截），建 `source_product`（`data_source=2`、`platform_type=1`、`source_product_url`、名称/主图/价格来自页面，**`freight_cost=8` 定值**）+ `source_sku` 行，回填映射。
   - **失效识别**：GONE_HINTS/页面打不开 → 照常建 `source_product` 行但 `source_status=0`、不建 SKU 行，进 `dead` 报告清单（这些是当下就有超卖风险的商品，首轮报告立即同步 owner）。
   - 纪律：3-5s/个 + 风控冷却（25min）、`--limit/--start/--dry-run` 断点续跑、`connect_cdp(9222, keep_urls=[myseller, item.upload])`、启动守卫（归类 v2/品牌/规格匹配不在跑）、每轮结束 log_work 留痕。**夜间轮次避开周六凌晨**（collect_full 到 P2 才退役，同窗会撞 9222）。

**验收**：`taobao_offer_map.source_product_id` 覆盖率 ≥99%（采集失败除外）；dead 清单交付；`--dry-run` 先行核数。

### P2 分级刷新 + 调度迁移

- **分级池选择**（detect_stock_change 新增 `--tiered` 模式，纯函数抽出便于单测）：
  - T1 每日池：`min(status=1 的 source_sku.stock) < 100`（`--t1-threshold` 可调）**或**从未刷新过；
  - T2 常规池：其余存活货源，按 `(id + day_of_year) % 7 == 0` 无状态轮转，每天 1/7；
  - T3 失效池：`source_status=0`，每周一复查，复活（拿到 SKU 数据）自动翻回 1 并销案；
  - `--max-per-run 1500` 保险上限。预估日常 ~1000 个/晚、1-1.5h。
- **采集时更新 `source_product.source_status`**：拿到 SKU 数据=1，GONE=0（dead 时不动 SKU）。
- **调度迁移**（绕开 crontab 不可写）：
  - 新增 LaunchAgent `com.spzx.stock-refresh`（**每日 03:00**）→ `run_stock_refresh.sh`（守卫同 inventory_cron：CDP 在线 + 归类 v2/品牌不在跑）；
  - `inventory_cron.sh`（crontab 05:00 行保留）**内部去掉 60 个池采集步骤**，仅保留 detect_alerts；脚本内注释注明采集已迁 03:00；
  - `cron_collect_full.sh` **内置退役开关**（进脚本直接 log 退役并退出），crontab 行物理保留；
  - `fetch_freight`（周六 03:30，9223）暂不动，运费定值化时一并处理。
- **四份副本一致性**：注册表 `ingest_dataset.source_stock_change.cron_expr` → `0 3 * * *`、`task-progress-config.json`、LaunchAgent、（crontab 行不动）全部对齐；`check-consistency.py` 必须绿。

**验收**：dry 模式打印三池数量合理；实跑一晚完成后抽 3 个 offer 对 1688 页面人工核对库存；`check-consistency.py` 0 fail。

### P3 失效告警 + 低库存页「货源失效」

- **detect_alerts.py 新规则 `source_dead`**：`source_status=0` 且 EXISTS 淘宝绑定 且无未解决同类告警 → 写 `sync_alert`（内容含货源名/offer_id/受影响淘宝 itemId 列表）；复活（source_status 翻回 1）→ 自动销案（status=2，沿用 ingest_stale 模式）。P1 发现的存量 dead 行在此期补告警。
- **后端**：`Product.java` 实体与 `LowStockRowVo` 加 `sourceStatus`（**动 spzx-model 必须 `mvn install -pl spzx-model` + 后端完整重启**，AGENTS 红线）；`LowStockMapper.xml` 加失效分支（筛选失效时忽略库存阈值，`WHERE sp.source_status=0 AND EXISTS 绑定`）；Service/Controller 加 `sourceDead` 查询参数（归一化仿 handleStatus：非法回默认）。`LowStockParamTest` 补参数归一化用例。
- **前端**（lowStock.vue）：「货源失效」筛选开关 + 红色「失效」徽标列；失效商品同样走现有 下架/删除/下架SKU 标记按钮（口径不变：留痕不代操作）。
- ⚠️ 预期管理：全量覆盖后低库存页「待处理」数量可能从 90 涨到数百——这是盲区浮出水面，不是故障。

**验收**：造一个 mock 失效行走通 告警→页面筛选→标记→复活销案 全链路；真实 dead 清单告警落地。

### P4 ISV 同步提频 + 0 库存行级核验

- **提频**：`com.spzx.stock-sync` plist 的 `StartCalendarInterval` 改为**数组三条**（05:30 / 12:30 / 19:30），同一作业三次触发；`run_stock_sync.sh` 守卫已有（CDP 在线 + 归类 v2/品牌/规格匹配不在跑，撞车跳过并写 cron_skipped）。注册表 `isv_stock_sync.cron_expr` 保持 `30 5 * * *` 为首跑时刻、备注三次触发；check-consistency 若对多时刻报漂移，按「同脚本多时刻取并集」口径调整该检查。
- **0 库存探针（实施第一步，门禁）**：取一个已知「0 库存且存活」的 offer 定向同步，读行级「同步记录」弹窗。**预期「库存同步为 0」；若 ISV 对 0 库存不推/推失败 → 停下，拿实测证据回报 owner 重新决策**（届时才讨论自动改淘宝库存的后备方案）。
- **行级核验**：新表 `stock_sync_check`（id/check_time/item_id/offer_id/record_text/verdict：1=成功同步为0、2=无同步记录、3=失败）。每轮同步后对**本地 0 库存活**商品（cap 50/轮）+ 随机 10 个对照，逐个开「同步记录」弹窗解析入库；verdict 2/3 → `sync_alert`（按天去重）。
- 解析函数纯函数化：样例「商品库存同步为352，M 白色规格库存同步为286」→ 逐 SKU 数字。

**验收**：探针通过（有截图/记录文本证据）；连续两轮核验表有数据、无未解释的 verdict=2。

## 6. 数据模型变更汇总

| 变更 | 内容 |
|---|------|
| `source_product` | + `source_status TINYINT NULL`（1正常/0失效/NULL未检测）；新建档行 `data_source=2`、`platform_type=1`、`freight_cost=8` |
| `stock_sync_check` | 新表（P4），DDL 落 `sql/stock_sync_check.sql` |
| `taobao_offer_map` | 仅数据回填（source_product_id），无结构变更 |
| `sync_alert` | 复用，新 alert 类型 `source_dead`（P3） |
| `source_sku` / `low_stock_handle` 语义 | 不变 |

## 7. 测试

- **Python 单测**（沿用现有纯函数测试风格）：分级池选择（T1 阈值/从未刷新/T2 取模轮转/T3 周检）、offer id 正则与补映射去重、GONE 判定、同步记录文本解析（含畸形输入）。
- **Java 单测**：`LowStockParamTest` 补 `sourceDead` 参数归一化；mapper SQL 原文钉（若新增 XML 分支）。
- **实测门**：单测禁止裸 `mvn test`（`-Dtest=` 指定 + `-am` + `-Dsurefire.failIfNoSpecifiedTests=false`）；每期实跑验收见各期「验收」。
- **一致性门**：每期收尾 `python3 scripts/check-consistency.py` 必须 0 fail（先 `--selftest` 证明门活着再信绿）。

## 8. 风险与未决

| 风险 | 缓解 |
|---|------|
| 1688 详情页批量风控（搜索页 ~5 次即冷却；详情页大批量未验证，周六全量采集佐证可行） | 3-5s 节奏 + 冷却 + 断点续跑 + 每轮报告；首轮慢速摸底 |
| ISV 对 0 库存的推送行为未知 | P4 探针门禁：不通过即停下回报，不带病上线 |
| 白天 ISV 同步与归类 v2/品牌抢 9222 | 现有守卫跳过 + cron_skipped 告警，宁可少跑不抢账号 |
| 建档后选品库统计口径变化 | D6 owner 知情；grade_quality 对 data_source=2 行为在实施首日核查一次 |
| spzx-model 实体变更 | mvn install + 完整重启（AGENTS 红线）；加列 NULL 缺省向后兼容 |
| 低库存页待处理数暴涨 | P3 预期管理；失效/低库存分池看，处理节奏 owner 掌控 |

## 9. 明确不做（Out of Scope）

- 自动下架淘宝商品、自动改淘宝 SKU 库存（D1 明确人工；仅当 P4 探针证明 ISV 推不了 0 时才回到 owner 重新决策）
- 运费采集/更新（D4：统一 8 元定值，后续单独处理）
- 抖音侧专门改造（`sync_douyin_stock` 自动受益，不动）
- 1688 价格变化的自动调价（`price_change` 告警维持现状）

## 10. 实施结果（2026-10-18，Task 13 收尾回填）

P1-P4 代码全部完成（Task 1-12），台账 `.superpowers/sdd/2026-10-18-source-stock-monitor/progress.md`。五件套验证全绿：Python 单测 5 个文件（test_offer_fetch / test_backfill_offer_archive / test_tiered_selection / test_detect_source_dead / test_isv_sync_verify）、`LowStockParamTest`（带 `-am`）、`check-consistency.py` 13 通过/3 警告/0 失败。

### P1 加列 + 补映射 + 全量建档

- `source_product.source_status` 已线上加列（列注释中文编码核对无双重编码）。
- `--remap` 补映射实测**回填 0 行**：3526 个 `source_product_id IS NULL` 映射行与 source_product（URL 含 offer）零交集——积压本来就无档可补，remap 路径没有存量可捡。
- 映射即进度实测（2026-10-18 晨）：`taobao_offer_map` distinct offer 3814，已映射（进池）**572**，待建档 **3242**。
- 试采 15 个（3+12 两轮小样）全成功：`source_status=1`、`freight_cost=8`、SKU 落库、映射回填、复采库存逐项一致。
- dead 存量：首轮真跑产出 `source_dead` 告警 **2 条**（sync_alert id=64/65）。
- ⚠️ **总覆盖验收 pending**：夜间分段 launcher 已挂（22:30 起、最多 4 夜、硬停 05:00 前、完成自退），全部建档完成后按验收口径（≥99%）补测。

### P2 分级刷新 + 调度迁移

- `--tiered` 三池 + `--stop-hour` 硬停钟上线；03:00 LaunchAgent `com.spzx.stock-refresh` 上线，kickstart 真采 **203** 实证全链路；`inventory_cron` 周一 05:00 仅告警模式真跑 rc=0；四份副本一致性门 13/3/0。

### P3 失效告警 + 页面

- `source_dead` 规则 + 复活销案上线；真实环境抓 2 个失效货源告警（id=64/65），幂等复跑新增 0。
- **复活销案补证（2026-10-18 Task 13，此前零实测）**：临时 `UPDATE source_product SET source_status=1 WHERE id=1835` → 跑 `detect_alerts.py --type source_dead` → 日志 `复活销案 alert=64`，alert 64 status **0→2**（对照行 65 未受影响）→ 还原 `source_status=0` + alert 64 回 status=0 → 复跑新增 0、终态与前置逐字一致（2 行均 status=0，无重复行）。
- 后端 `sourceDead` 参数 + 失效筛选视图（total=2 实证），`LowStockParamTest` 10/10；前端失效筛选/徽标接线 grep 实证。

### P4 提频 + 核验

- `com.spzx.stock-sync` plist 三时刻（05:30/12:30/19:30）上线；每轮同步后自动接跑 `isv_sync_verify.py --cap 50`。
- **探针门禁通过**：ISV 会把 0 库存推成淘宝 0（商品 1023052654615 的 10-17 同步记录 42 处「同步为0」逐 SKU=本地库存、Σ=165 吻合；证据=抽屉 innerText 存档）。D1 人工下架维持。
- 核验实测：`--cap 3` 真跑 **3/3 verdict=1**（零库存目标全部核验成功）；对照池已排混合库存商品（混库行搜不到会沉淀假 verdict=3）。
- 未决（Task 11 parked）：935918678330 类商品（0 库存晚于最后同步）需「最后同步时间 vs 变 0 时间」升级判据，owner 定。
