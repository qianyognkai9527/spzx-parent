# Spec：在售口径收敛 + 调度重组（2026-10-19）

状态：待 owner 评审
前置：2026-10-19 中午静默窗口侦察（结论见 §1），chrome_guard.sh A 方案守卫已落地

## 1. 背景与实测依据

中午窗口（12:03-13:57）只读探针结论：

- 控制台快捷筛选自带全套口径：**销售中(889)** / 仓库中(2947) / 已关联货源(3831) / 关联货源已下架(222) / 价格倒挂(60)
- 点「商品状态： 销售中」是**前端过滤**（零网络请求），数据在初始加载里；行内直接带：店铺商品 ID、店铺商品状态、**货源状态/货源价格/货源库存**
- 当前分级刷新池 970 = 存活+有URL，其中 963 有淘宝绑定——大量绑定指向「仓库中」商品，刷新在白烧
- 直连 SKU API（h5api.m.1688.com）是 JSONP，fetch 被 CORS 拦；可解（JSONP 注入+sign 重算）但**不优先**——列表数据已够
- 探针实测两个病，已在当天修/立规：① 脚本退出把标签关光 → 0 标签病态，connect 必报错（补守卫 tab 恢复）；② nohup 一次性定时会被工具会话回收 → 一次性调度一律 launchd

同日已落地（A 方案第一步）：`automation/sourcing/chrome_guard.sh` 的 `ensure_chrome`（不在线→静默拉起+minimize；0 标签→补守卫 tab），接入 5 个 cron 包装脚本；`inventory_cron.sh` 的假 Chrome 守卫移除（它只剩纯 DB 的 detect_alerts）。实测冷起 6s、二次调用幂等。

## 2. 目标

1. 三个 Chrome 定时任务（库存同步/推广日报/分级刷新）只处理**在售（销售中 889）**
2. 中午静默窗口固化为日常调度；推广日报挪 12:06 且**只采 D-1 及以前**
3. 分级刷新从「970 次整页加载/夜（≈6h）」降为「列表扫描 2 分钟 + 每夜 40 个详情页抽查」
4. 产出超卖告警数据地基（`oversell_risk`/`low_stock`），供 Spec 2 首页板块消费

## 3. 架构

### 3.1 sync_onsale.py（新脚本，每天 12:40）
连 9222（ensure_chrome）→ 已关联货源 → 点「商品状态： 销售中」→ 逐页（889÷100=9 页）DOM 抽取每行：
`taobao_item_id / 店铺商品状态 / 货源状态 / 货源价格 / 货源库存`，offerId 经 `taobao_offer_map` 反查 `source_product_id`。

- 落库：新表 `onsale_snapshot`（snapshot_date, taobao_item_id, source_product_id, source_status, source_stock, source_price, raw），按 (snapshot_date, item_id) 幂等 upsert，每日全量快照
- 绑定对账：当日快照 vs 昨日快照，新增/消失的在售绑定写 `sync_alert`（type=`onsale_binding_change`，按天去重）
- **退出前必须补守卫 tab**（§1 病①）
- 台账：`ingest_batch` 新 dataset code `onsale_scan`，注册表+卡片登记

### 3.2 isv_stock_sync.py 在售化（12:30 / 19:30 轮）
流程改为：点「商品状态： 销售中」→ 翻 9 页 → 每页全选 → 批量同步库存 → 确定。
写操作量 4134 行/轮 → 889 行/轮（-78%）。`run_stock_sync.sh` 的守卫/台账/核验（isv_sync_verify）不动。

### 3.3 detect_stock_change.py 改造（夜 22:30，M2 切换）
- 主数据源切换为控制台快照（sync_onsale 产出）：T1/T2/T3 轮转**废弃**，在售池全覆盖靠 12:40 扫描
- 每夜抽查：从在售池轮转抽 **40 个**开详情页（35s/个 ≈ 25min），SKU 级 canBookCount 刷新 `source_sku`；与控制台值不一致 → 以详情页为准 + 写告警（控制台撒谎检测，10 样本连续一致才允许 M1→M2 切换）
- dead 落库：控制台「关联货源已下架」chip 计数 + 货源状态列 → `source_status=0` 直接写，不再开页面验证；复活路径同步
- 22:30 起跑（ensure_chrome 自启），全程 ≈ 30min

### 3.4 collect_alimama_promo（22:00 → 12:06）
- **日期口径：end_date=昨天，当日不采**；次日 12:06 重拉 15 天滚动 upsert 补全
- 挪进中午窗口（12:03 首任务 ensure_chrome 拉起），晚间饿死/互撞风险消除
- 四份副本同步：`com.spzx.alimama-promo.plist`（22:00→12:06）+ 注册表 `cron_expr` + 卡片 + `~/docs/cron.md`

### 3.5 Chrome 生命周期收尾
- launchd 作业 `com.spzx.chrome-kill`：**13:57 与 05:10** 各一次，kill 前检查无任务 python 进程在跑（在跑则本次放过并写 `sync_alert` 提示）
- probe_noon_recon 等一次性脚本并入规范：退出前 ensure 守卫 tab

### 3.6 告警数据（Spec 2 消费）
`sync_alert` 新增两类，由 sync_onsale 当轮判定（销案与 source_dead 同模式，复活自动 status=2）：
- `oversell_risk`：在售商品但其货源 `source_status=0` 或 `source_stock=0`
- `low_stock`：在售商品其货源 `source_stock ≤ 阈值`（默认 10，可调）

## 4. 测试与验收

- 行解析/快照 upsert/告警判定抽成纯函数 + 单测（venv python 直跑）
- sync_onsale 首跑 `--dry-run`（只抽第 1 页不落库）→ owner 看数据 → 放开全量
- M1→M2 切换判据：抽查 10 样本控制台值 vs 详情页值连续 3 天一致
- `python3 scripts/check-consistency.py` 全绿（四份副本对齐）
- 一轮完整中午窗口观察：12:03 自启 → 12:06 alimama → 12:30 sync(9页) → 12:40 onsale → 13:57 kill

## 5. 分期

- **M1**：sync_onsale + isv_stock_sync 在售化 + alimama 挪 12:06/D-1 口径 + chrome-kill 作业 + 台账四份对齐
- **M2**：detect_stock_change 切抽查模式（M1 稳定 3 天后）
- **Spec 2（另开）**：首页板块化 + 超卖告警卡 UI（含视觉稿）
