# 调度体系优化设计 —— 两窗口 + 事件驱动 + 可靠性四件套（2026-10-19）

状态：设计稿（brainstorming 已选定方案 A，待 owner 审阅后转实施计划）
前置：`2026-10-19-onsale-refactor-design.md`（M1/M2 已落地）；本 spec 沿用其快照/夜巡/同步组件。

---

## 1. 背景与证据（近三天日志实证）

| # | 问题 | 证据 |
|---|------|------|
| E1 | **守卫可无限饿死任务**：共享 9222 的定时任务用无时限 `pgrep && skip`，任何 hung 进程能让同窗任务天天跳过 | `cron_alimama_promo.sh` L40、`run_stock_sync.sh` L26-36；推广日报 10-17/10-18 连续两晚 22:00 被跳过（最后一跳成功 10-16），数据断 3 天；skip() 写告警+failed 台账后 **exit 0 静默退场**，无升级机制 |
| E2 | **写暴露面过大**：isv_stock_sync 全量 39 页×3 轮/天（05:30/12:30/19:30），全是「全选→批量同步」写操作 | `com.spzx.stock-sync.plist` 三时刻；10-17 05:30 实跑 42 页 4199 绑定项 |
| E3 | **rc=6「本页全选已选0/100」瞬态失败**无就地重试，靠下一轮全量重跑自愈 | 10-17 page 33、10-19 12:30 page 33（同页复发）；`isv_stock_sync.py` L273-274 校验失败直接判页失败 |
| E4 | **登录态失效秒败**（rc=2）无预检、告警不指因 | 10-18 05:30 rc=2 即退（42 页 0 产出）；`ensure_chrome` 只保 Chrome 活不保登录态 |
| E5 | **backfill 建档与凌晨窗口冲突** | 10-19 03:00 夜巡被 `pgrep backfill_offer_archive` 守卫 skip（sync_alert cron_skipped 03:00:05）；建档 launcher 进程已死但**待建档还剩 621**（10-19 04:03 夜1 清了 2511→600） |
| E6 | 僵尸调度残留 | crontab `0 3 * * 6 cron_collect_full.sh`（脚本已内置退役，白占周六 03:00）；`~/Library/LaunchAgents/com.spzx.sku-match.plist` 未加载且 `StartCalendarInterval` 键损坏 |
| E7 | **磁盘堆积无回收**：数据卷 94%（460GB 仅剩 27GB）；截图/日志只增不删 | 截图 2 个写入点：`auto_list.py`（`test_screenshot_<ts>.png` / `submit_unknown_<ts>.png`，时间戳命名**永久累积**）、`sycm_item_snapshot.py`（/tmp/sycm_noapi.png 单文件覆盖）；全部 cron 日志 `>>` 追加无上限（当前各自 <1MB，但周月级会涨）；真正大头 chrome-profile 1.8GB（登录态，**不可清**）、pdd_images 185MB（**输入素材，不可清**——3003 张误提交教训） |

改动前的时刻表（2026-10-19 实测盘点，含调度源）：

| 时刻 | 任务 | 调度源 | 性质 |
|------|------|--------|------|
| 每小时 | task_stats | crontab `0 *` | 纯 DB |
| 03:00 | 夜巡 detect_stock_night | LaunchAgent stock-refresh | 只读详情页 |
| 03:00(周六) | collect_full 僵尸 | crontab | 已退役 |
| 04:30 | db_daily（备份→验证→detect_alerts→质量分级） | crontab `30 4` | 纯 DB |
| 05:10 | 收 9222 | LaunchAgent chrome-kill | — |
| 05:30 / 12:30 / 19:30 | ISV 库存同步（**写**，39 页） | LaunchAgent stock-sync | 写 |
| 06:00 | 生意参谋快照 | crontab `0 6` | 只读 |
| 12:06 | 推广日报（15 天滚动） | LaunchAgent alimama-promo | 只读 |
| 12:40 | 在售扫描 → onsale_snapshot | LaunchAgent onsale-scan | 只读 |
| 13:57 | 收 9222 | LaunchAgent chrome-kill | — |
| 22:30→05:00 | backfill 建档（临时，launcher 已死） | 无（需手动重启） | **写**（建档） |
| 23:30 | daily_schedule | LaunchAgent daily-schedule | 纯 DB |

## 2. 目标与非目标

- **目标（owner 排序）**：① 风控最小化——削减写操作频次与页面数、错峰、抖动；② 可靠——饿死/瞬态失败/静默跳过三类问题收敛到「要么跑成，要么大声告警且不无限重复」；③ 效率——Chrome 起停集中在两个窗口，白天空闲。
- **非目标**：不做自动重登录（扫码/滑块必须人工，红线）；不动 9223/9224（抖店/PDD 链路另议）；不建新表；不做外部 IM 推送（owner 已拒绝）。
- **已接受的代价**：库存同步新鲜度从 ≤8h 放宽到基线 24h（事件驱动在有事时当晚 19:30 补，响应 ≤7h）。

## 3. 总体设计：改造后时刻表

原则：**凌晨=唯一日常写窗口（链式串行）；中午=纯只读窗口；傍晚=事件驱动补偿；其余时间 9222 关着**。

| 时刻 | 任务 | 调度源（改造后） | 变化 |
|------|------|------------------|------|
| 21:30→02:45 | backfill 建档收尾（临时，621 个） | `run_backfill_nights.sh` 手动 nohup 重启（窗口 22:30→21:30，alarm 20000s→18900s） | 改窗口，避开 03:00 夜窗 |
| **03:00(±5min)** | **夜窗链**：夜巡 → ISV库存同步(9页) → 收 9222 | LaunchAgent stock-refresh 改指 **`run_night_window.sh`**（新，字面调用 run_stock_refresh.sh + run_stock_sync.sh + chrome_kill.sh） | **对已批准方案的一处细化**：原「03:40 定时同步」改为「夜巡完成后链式接续」——夜巡最坏 2h（174 页×65s 超时上限）会撞死 03:40 定时触发；链式后同步永远跟在夜巡后，且凌晨不再有第二个定时器 |
| 04:30 | db_daily 四合一 | crontab（不变） | 不变 |
| 12:06(±5min) | 推广日报 | LaunchAgent alimama-promo（不变） | +抖动 |
| 12:35(±3min) | 生意参谋快照 | crontab `0 6` → `35 12` | **06:00→12:35**，让凌晨窗口只剩写、中午纯只读 |
| 12:50(±3min) | 在售扫描 | LaunchAgent onsale-scan 12:40→12:50 | 顺延避开 sycm |
| 13:10 | 收 9222 | LaunchAgent chrome-kill：13:57→13:10，**删 05:10 条目**（夜窗链末尾自己收） | — |
| 19:30 | **事件驱动补偿**（新 `run_stock_event_sync.sh`） | LaunchAgent stock-sync 三时刻→仅 19:30，改指新包装 | 见 §5 |
| 23:30 | daily_schedule | 不变 | — |

时刻选择依据：alimama 实测 4-15min（10-16 22:00→22:04，防僵死上限 120min 兜底）、sycm 实测 ~2.5min（06:00→06:02:41）、onsale ~5min（9 页）、夜巡常态 30-50min（164 低库存+10 对照，delay 5s）、同步 9 页 10-15min（含重试）。12:06+15min=12:21 < 12:35-3min=12:32，余量 11min。

**写暴露面量化**：同步从 39 页×3 轮=117 页/天 → 9 页×1 轮 + 事件日 +9 页 = **9~18 页/天（-85~92%）**；加上 backfill 收尾（临时 ~2h×1 晚）后回落常态。

## 4. 可靠性四件套

### 4.1 防僵死守卫 `guard_task <pattern> <max_minutes>`（放 chrome_guard.sh）
- 进程不在 → 放行；在且 `ps -o etime` ≤ max → skip（正常避让）；**> max → 视为 hung：`pkill -TERM` 等 10s 仍活再 `pkill -KILL`，写 cron_failed 告警（带 pattern 与 age），返回放行**。
- 只杀 python 子进程（不杀 wrapper）——wrapper 醒来后走自己的 rc≠0 路径写 failed 台账，台账链完整、告警由 cron_alert 按天去重。
- **只用于定时任务模式**：`sycm_item_snapshot` 60m、`collect_alimama_promo` 120m、`isv_stock_sync` 60m、`sync_onsale` 30m、`detect_stock_night` 130m、`backfill_offer_archive` 340m（夜窗 21:30-02:45 自有 alarm 硬停，守卫兜底）。
- **用户长任务（归类v2/品牌批处理/规格匹配）保持纯 `pgrep && skip` 不杀**——它们是合法小时级长跑，杀掉=破坏断点续跑。

### 4.2 连续跳过升级
- 各 wrapper `skip()` 增加计数：`/tmp/spzx_skipcnt_<key>` +1，成功路径清零；≥2 时告警 msg 前缀加「**【已连续 N 天未跑】数据断档，需人工介入**」。
- 计数文件放 /tmp（重启清零可接受：升级文案晚一天出现不致命），不进库不建表。

### 4.3 rc=6 当页重试×2（isv_stock_sync.py）
- 「已选 n/0」校验失败 → `wait_no_modal` 清弹窗残留 → 重新导航本页 → 重新全选 → 复验，**同页最多重试 2 次**，仍败才按原 rc=6 退出。
- 不做整轮自动重跑（写暴露翻倍违背目标①）；当天兜底=19:30 事件检查（见 §5 规则 b）。

### 4.4 登录态预检 `ensure_login`（chrome_guard.sh + check_login.py）
- playwright 连 9222 → 开 ufuwu 控制台 URL → 判定登录墙（最终 URL 跳 login.*.taobao.com / 页面含登录表单标志）→ 失败：写显式告警「**9222 登录态失效，需人工扫码**」并 skip 本轮（E4 的 rc=2 从此有指因告警，且不空烧一轮）。
- **不自动重登录**。全部 5 个定时包装（夜窗链内两任务、alimama、sycm、onsale、事件补偿）接入；顺序固定 `ensure_chrome && ensure_login || skip`。
- 成本 ~10s/轮×6 轮/天，可接受。

### 4.5 抖动
- 各定时包装开头 `sleep $((RANDOM % N))`：窗口首任务（03:00 夜窗、12:06 alimama）N=300s；后续相邻任务（sycm/onsale）N=180s。launchd/crontab 不支持原生抖动，包装层实现。

## 5. 19:30 事件驱动补偿口径

`run_stock_event_sync.sh`（新）纯 DB 判定，**无事件不拉 Chrome、不写任何台账行、日志一行「无库存事件」退出**：

> 触发 = 以下任一：
> a) **当天新写**（`DATE(create_time)=今天`）且未读的 `sync_alert`，`alert_type ∈ {isv_sync_fail, source_dead, onsale_binding_change, onsale_mismatch}`；
> b) 今天 `ingest_batch.dataset='isv_stock_sync'` **无 success 批次**（03:40 夜窗没跑成/没跑）。

- 限定「当天新写」是刻意的：陈年未读（如累计 184 条 source_dead）若也计数，19:30 会天天触发、事件驱动失效；当天新写=「今天确实发生了需要推送的事」，次日既使仍未读也不再触发（各写侧本就按天去重）。
- **白名单收窄（2026-10-19 owner）**：`low_stock`/`oversell_risk` 属中午扫描每天重算的常规状态，留在事件集会让 19:30 天天触发、退化成日常同步，故移出（6→4 类）。**当日超卖保护由次日 03:00 基线同步兜底**，与已接受的 24h 新鲜度一致。

- 有事件 → `ensure_chrome && ensure_login` → guard_task → 复用 `run_stock_sync.sh`（9 页在售口径）→ 收 Chrome。
- 不触发事件集的：`ingest_stale`、`cron_skipped`、`cron_failed`（后者通过规则 b 间接覆盖自家失败）。
- **新鲜度面板注记**：无事件日 19:30 无 isv_stock_sync 批次属预期，`ingest_dataset.cron_expr` 登记为基线 `45 3 * * *`，口径写在注册表 remark，防误读「漏跑」。

## 6. 组件改动清单

| 文件 | 改动 |
|------|------|
| `automation/sourcing/run_night_window.sh` | **新建**：抖动 → run_stock_refresh.sh → run_stock_sync.sh → chrome_kill.sh；任一步 rc≠0 不拦后步（各自已有台账/告警），仅记行 |
| `automation/sourcing/chrome_guard.sh` | +`guard_task`、+`ensure_login`（配套 check_login.py）、skip 计数函数 |
| `automation/sourcing/check_login.py` | **新建**：playwright 登录墙探测，exit 0/1 |
| `automation/sourcing/run_stock_sync.sh` | 守卫换 guard_task（isv_stock_sync 60m）；skip() 接计数升级；+ensure_login |
| `automation/sourcing/run_stock_refresh.sh` | 守卫换 guard_task（detect_stock_night 130m）；skip() 接计数 |
| `automation/sourcing/run_onsale_scan.sh` | 守卫换 guard_task（sync_onsale 30m / sycm 60m / alimama 120m）；skip() 接计数；+ensure_login |
| `automation/sourcing/cron_sycm_snapshot.sh` | 守卫换 guard_task（sycm 60m / alimama 120m）；skip() 接计数；+ensure_login |
| `automation/tb-auto/cron_alimama_promo.sh` | 守卫换 guard_task；skip() 接计数；+ensure_login |
| `automation/sourcing/isv_stock_sync.py` | rc=6 当页重试×2（§4.3） |
| `automation/sourcing/run_stock_event_sync.sh` | **新建**：§5 判定 + 条件执行 |
| `.superpowers/sdd/2026-10-18-source-stock-monitor/run_backfill_nights.sh` | 等待时刻 22:30→21:30（删等 alimama 循环）、alarm 20000→18900；**当天 nohup 重启**（launcher 已死，死因先查 backfill_nights.log） |
| `~/Library/LaunchAgents/com.spzx.stock-refresh.plist` | 03:00 不变，Program → run_night_window.sh（仓库副本 `scripts/launchd/` 同步） |
| `~/Library/LaunchAgents/com.spzx.stock-sync.plist` | 删 05:30/12:30 条目，19:30 Program → run_stock_event_sync.sh |
| `~/Library/LaunchAgents/com.spzx.chrome-kill.plist` | 13:57→13:10，删 05:10 |
| `~/Library/LaunchAgents/com.spzx.onsale-scan.plist` | 12:40→12:50 |
| `~/Library/LaunchAgents/com.spzx.sku-match.plist` | **删除**（未加载、键损坏的残留） |
| crontab | `0 6` sycm → `35 12`；删 `0 3 * * 6 cron_collect_full.sh`；修 05:00/05:30 过期注释。⚠️ 本机 `crontab <file>` 曾挂死（2026-10-07），但 2026-10-19 编辑成功过——操作带超时兜底，卡住即弃并改走 LaunchAgent 方案 |
| `scripts/mysql-cnf.py` 无关 | — |
| 注册表 `ingest_dataset.cron_expr` | sycm→`35 12 * * *`、isv_stock_sync→`45 3 * * *`（+remark 事件驱动说明） |
| `automation/sourcing/task-progress-config.json` | 卡片时刻同步 |
| `~/docs/cron.md` | 八模块速查表（2026-10-19 改造后版）按新时刻更新；backfill 行标注「临时，完成自退」 |
| `scripts/cleanup_runtime.sh` | **新建**：§9 磁盘卫生，支持 --dry-run |
| `scripts/db_daily.sh` | +第 5 步调 cleanup_runtime.sh |
| plist 操作纪律 | 改用整体重写 XML（PlistBuddy 嵌套 `-c` 会写坏整份文件）；`plutil -lint` + `launchctl bootout/bootstrap` 重载 + `launchctl print` 逐字段核对；两份副本 `cmp` |

## 7. 验收判据（明天 2026-10-20 逐项核）

1. 夜窗：`/tmp/stock_refresh_cron.log` 出现 SUMMARY checked>0 → 紧接 `/tmp/stock_sync_cron.log` 「ISV库存同步 开始/结束 rc=0 rows≈4000+」→ `/tmp/chrome_kill.log` 03~05 点「已收 9222」。
2. db_daily 04:30 rc=0（四步全 rc=0）。
3. 中午：alimama 开始且 10-17~10-19 断档被 15 天滚动回补覆盖；sycm `35 12` 触发 ~283 行（verdict 非 partial）；onsale 入库 ≈889 行；13:10 收 Chrome。
4. 19:30：有事件→补跑 success；无事件→日志「无库存事件」且无新台账行。
5. sync_alert 不再出现「9222 上有其他采集任务在跑」连续两天同 key（除非真有占用）。
6. `python3 scripts/check-consistency.py` 全绿（四份调度副本对齐：crontab/LaunchAgents/注册表/卡片）。
7. backfill 完成后 `taobao_offer_map` 待建档=0，launcher 自退，9222 夜窗独占。
8. cleanup_runtime.sh：`--dry-run` 清单 owner 过目后实删一次，`/tmp/cleanup_runtime.log` 有「删除 N 个、释放 X MB」行；chrome-profile/pdd_images 零触碰（对照文件数前后不变）。

## 8. 风险与回滚

- **链式夜窗单点**：run_night_window.sh 语法错 = 当天无同步。缓解：上线当天白天先手动执行一次全链验证；inner 脚本各自守卫/台账不变，链坏不影响数据正确性只影响时点。
- **守卫误杀**：max 阈值均 ≥ 正常耗时 2 倍以上；被杀任务走 failed 台账+告警，次日自愈。用户长任务白名单明确不杀。
- **回滚**：plist 旧定义都在 git（`scripts/launchd/`）与本文档 §改动前表；恢复 = 改回 ProgramArguments/时刻 + bootout/bootstrap。crontab 改动前先 `crontab -l > /tmp/crontab.bak.20261019`。
- **backfill 重启风险**：断点续跑幂等（映射即进度），重复跑无害；夜1 实测 10.4s/个，621 个 ~1.8h，一晚必完。

## 9. 磁盘卫生（owner 2026-10-19 追加需求）

新脚本 `scripts/cleanup_runtime.sh`，作为 **db_daily.sh 第 5 步**（04:30，纯文件操作，不碰 Chrome，不新增调度入口），支持 `--dry-run`（打印将删清单与可释放量，不删）：

1. **日志裁剪**（truncate 保尾）：白名单内的 /tmp 运行日志（cron_stats、sycm_daily_cron、alimama_promo_cron、stock_sync_cron、stock_refresh_cron、onsale_scan、inventory_cron、inventory_weekly、chrome_kill、backfill_night_run、db_daily、cleanup_runtime 自身等 spzx 系）超过 2MB 时只保留末尾 2000 行——保留「最近的开始/结束/rc 行」，丢中段历史可接受（台账真源在 ingest_batch，不在日志）。
2. **截图清理**（模式白名单 + 7 天）：`automation/tb-auto/test_screenshot_*.png`、`submit_unknown_*.png`、`/tmp/sycm_noapi.png`，mtime > 7 天删除。**禁止任何 `automation/**/*.png` 全域按扩展名扫删**——pdd_images 等输入素材混在图片扩展名里（3003 张教训）。
3. **/tmp 探针残留**：已知 spzx 前缀（`spzx_*`、`noon_*`、`sku_direct_probe*`、`*_probe.json`）mtime > 14 天删除。
4. **绝不触碰**：chrome-profile*（登录态红线）、pdd_images*、novel_batches、douyin_reports、`~/Backups/spzx-db/`（有自己的 7 天/8 周轮转）、gitignore 的业务数据 jsonl/json。
5. 首跑纪律：先 `--dry-run` 给 owner 过目清单，再实删；此后每天 04:30 自动跑，输出「删除 N 个文件、释放 X MB」进 `/tmp/cleanup_runtime.log`。
6. **纪律条款（进 automation/AGENTS.md）**：今后任何脚本新增截图/快照落盘点，必须登记进 cleanup_runtime.sh 的模式白名单，否则视为 bug。

> 真正的磁盘大头不在截图/日志（当前合计 <10MB），是 chrome-profile 1.8GB + pdd_images 185MB + 各类业务数据——本次不动；若后续仍紧张，另立议题（如 chrome-profile 缓存子目录清洗，需逐项验证不伤登录态）。

## 10. 待观察（不阻塞上线）

- 夜巡真实耗时（今晚首跑拿到后校准 03:00→同步接续的时间线）。
- 事件驱动 19:30 的触发频率（若天天触发说明基线 1 轮不够，再议）。
- 中午窗口三任务在抖动下的实际间隔（alimama 若常见 >25min，把 sycm 再顺延）。
