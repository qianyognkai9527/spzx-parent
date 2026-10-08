# 工作留痕 → 日程管理（work_log）设计

日期：2026-10-08
状态：已评审并落地（本 spec 未提交 git —— 用户明确「不要执行任何 git 提交」）

## 1. 背景与目标

后端「日程管理」（`sys_user_schedule` + `sys_user_schedule_task`）目前**只有一份**每天 23:30 由
`scripts/daily_schedule.py` 写入的自动台账，来源是 6 类**有事实痕迹**的数据：

1. `ingest_batch` 定时任务跑批（轮次/成功/少一批/失败 + 行数）
2. `sync_alert` 当天新增告警
3. `platform_product` 商品登记
4. `product_media` / `source_product` 当日质量分
5. `novel_chapter.published_at` 小说发布
6. 后端 + 前端两个仓库的 `git log`

**缺口**：我们手做的自动化工作（淘宝归类 v2、品牌/标题批处理、PDD 铺货、1688 选品、AI 选词、
图片下载、对账/推广 CSV 手工导入等）**没有 commit 就不进日程**，事后无从「排查漏做的任务」。

**目标**：每完成一件工作 / 长任务告一段落，**立即**把它连同**数据进度**写入当天日程，并按
**模块**归类，方便日后按模块排查漏做。

## 2. 需求决策（已与用户确认）

| # | 决策 | 结论 |
|---|------|------|
| 1 | 记录方式 | 方案 A：提供命令行工具 `scripts/log_work.py`，由 AI 每完成一件活即调用 |
| 2 | 数据进度来源 | 方案 C：能给进度文件就自动解析；给不出就把手填文本原样写入 |
| 3 | 同日重复记录 | 方案 C 变体：默认**追加**（保留时间线）；带 `--merge` 时按「同模块+同标题」**原地更新** |
| 4 | 任务模块 | 方案 A：每条记录带**模块标签**，页面按模块分组/筛选；**自由文本**（AGENTS.md 列建议清单，不强制） |
| 5 | 模块存储 | 方案 A：`sys_user_schedule_task` 加 `module varchar(30)` 列（动表 + 实体 + 前端） |
| 6 | 幂等唯一键 | **不新增 `biz_key` 列**；以「同一天 + `create_by=-1` + 模块 + 标题」作为合并键 |

## 3. 总体方案

新增 `scripts/log_work.py` 命令行工具，直写当天日程；配套加一列 `module`；`daily_schedule.py`
修一处口径；前端详情弹窗加模块列 + 筛选/分组。**不新增后端接口**，不改调度（cron / LaunchAgent /
注册表 / 卡片）。

### 3.1 记录归属与冲突隔离（关键约束）

- `daily_schedule.py` 每天 23:30 会 `DELETE FROM sys_user_schedule_task WHERE schedule_id=? AND create_by=0`
  后重建自动条目。
- 因此 `log_work.py` 写的行使用 **`create_by = -1`**（新哨兵，含义「AI/手工代记」），
  **天然不被 23:30 的清理删掉**。页面上人工加的条目仍是用户 id（≥1）。
- `sort` 用 **1000+** 段，保证排在自动条目（1..N）之后。
- 不写 `ingest_batch`、不注册 `ingest_dataset`（它不是定时作业，免得污染「应跑」口径与
  `check-consistency.py` 的调度对齐检查）。

## 4. 详细设计

### 4.1 数据库变更

新增迁移脚本 `spzx-manager/src/main/resources/sql/`（或 `sql/`，随仓库既有习惯）：

```sql
ALTER TABLE sys_user_schedule_task
  ADD COLUMN module VARCHAR(30) NULL COMMENT '任务模块（自由文本，AI 留痕用）' AFTER task_title;
```

- 自动台账写入的行 `module = NULL`；前端显示为「（自动/定时）」。
- 幂等：迁移脚本用 `information_schema` 判存在再 ALTER，可重复执行。

### 4.2 `spzx-model` 实体

`SysUserScheduleTask.java` 在 `taskTitle` 之后加字段：

```java
@Schema(description = "任务模块（自由文本）")
@TableField("module")
private String module;
```

> 改 `spzx-model`（jar 进 classpath）后必须 `mvn install -pl spzx-model -DskipTests` 并**完整重启后端**，
> devtools 热重启不够。

### 4.3 `scripts/log_work.py`

复用 `daily_schedule.py` 的连接方式（`sys.path` 加 `automation/sourcing`，`from cron_batch import connect`），
不新抄一份凭据。

**命令行**：

```
log_work.py --module 淘宝归类 --title "归类v2 第N轮" \
  [--remark "调价仅家居服/美甲"] \
  [--progress-file automation/sourcing/shop_cat_v2_progress.json] \
  [--progress "自由文本补充"] \
  [--merge] [--ratio 90] [--incomplete] \
  [--date YYYY-MM-DD] [--user 1] [--dry-run]
```

- `--module`、`--title` 必填。
- **进度解析**（`--progress-file`）：读 JSON，顶层 dict 中每个值为 `list` 或 `dict` 的键取
  `len()`，拼成 `done 1464 / skipped 1339 / failed 1079`。实测三份目标文件形如：
  - `shop_cat_v2_progress.json` → `{done:[…], skipped:[…], noprice:[], failed:{…}, sizegap:{}}`
  - `brand_title_progress.json` → `{done:[…], skipped:[], failed:{…}}`
  - `pdd_create_progress_1688.json` → `{done:[…], failed:{…}, skipped:[], captcha:{…}}`
  解析不出（文件缺失/非预期结构）就跳过并在 stderr 提示，不报错退出。
- `--progress` 文本追加在文件解析结果之后；两者都给则「文件在前、文本在后」。
- `--incomplete`（可配 `--ratio 0..100`）→ `is_complete=0`，`complete_ratio=ratio`；默认 `is_complete=1`、`complete_ratio=100`。
- 写入 `remark = 进度串 + " " + 手填备注`，截断到 varchar(500)。

**落库逻辑**：

1. `SELECT id FROM sys_user_schedule WHERE user_id=? AND date_str=? ORDER BY id LIMIT 1`；
   无则 `INSERT`（`task_count=0, complete_count=0, status=0, create_by=<user>`）。
2. 若 `--merge`：
   `SELECT id FROM sys_user_schedule_task WHERE schedule_id=? AND create_by=-1 AND module<=>? AND task_title=? AND status=0 LIMIT 1`
   命中 → `UPDATE` 标题/模块/进度/`is_complete`/`update_time=NOW()`；未命中 → `INSERT`。
3. 默认（无 `--merge`）：直接 `INSERT`，`sort = 1000 + (当天 create_by=-1 行数)`。
4. 重算父表 `task_count`/`complete_count`：`SELECT COUNT(*), SUM(is_complete=1) FROM sys_user_schedule_task WHERE schedule_id=? AND status=0`（与
   `daily_schedule.py`、Java `SysUserScheduleTaskServiceImpl.updateCompleteValue` 三处同算法），
   并 `UPDATE` 父表。父表 `remark` 更新为 `"N 项：M 项已完成"`（口径见 4.4）。
5. 打印一行确认，例如：
   `已记入 2026-10-08 日程：淘宝归类 | 归类v2 第N轮 | done 1464 / skipped 1339 / failed 1079`。
6. `--dry-run` 只打印将写什么，不落库。
7. 幂等说明：**同一天同一模块+标题 + `--merge`** 只留一条并刷新进度；不带 `--merge` 每次都追加，
   保留每轮时间线。

**模块建议清单（自由文本，不强制）**：淘宝归类、品牌标题、PDD铺货、1688选品、AI选词、
视频生成、对账、小说、系统、其它。写进 AGENTS.md 供参照，脚本不校验。

### 4.4 `daily_schedule.py` 一处口径修正

现状：`upsert_day()` 里父表 `remark = "%d 项：%d 项已完成" % (len(tasks), …)`，`tasks` **只含自动条目**，
而 `task_count`/`complete_count` 数**全部** `status=0` 行。一旦当天有 `log_work` 手工条目，
「N 项」与「任务总数」对不上（吓自己也误导排查）。

修正：`remark` 改为在插入/清理完成后、按 DB 全量重算的 `task_count`/`complete_count` 生成。
自动条目的删改逻辑（`DELETE ... create_by=0`）**保持不变**，故 `create_by=-1` 的手工条目无损。

### 4.5 前端 `userSchedule.vue`

- 详情弹窗（子任务表）加「模块」列；`module` 为空显示 `（自动/定时）` 灰字。
- 详情弹窗顶部加「按模块筛选」下拉，选项从当前子弹窗 distinct `module` 动态生成（含「全部」）。
- 加「按模块分组」开关：开时按模块折叠分组显示（组头显示模块名 + 该组条数/完成数）。
- 「新增/编辑子任务」表单加可选「模块」输入框（页面手工加也能打标）。
- 父级日程列表页**不改**（模块是子任务维度）。

### 4.6 AGENTS.md

- 根 `AGENTS.md`：在「定时任务」/「日常」相关段落加规则——
  *每完成一项工作或长任务告一段落，立即用 `python3 scripts/log_work.py ...` 记入当天日程；
  长任务用 `--merge` 合并当天一条、零散小活直接追加；模块用建议清单里的中文名。*
- `automation/sourcing/AGENTS.md`：加同款提示 + 常用调用样例（归类 v2 / 品牌 / PDD / 选品）。

## 5. 验证

1. `mvn install -pl spzx-model -DskipTests -q` → `mvn compile -pl spzx-manager -am`；**重启后端**。
2. `python3 scripts/log_work.py --module 测试 --title "留痕自测" --progress "done 3 / failed 1" --dry-run` 看输出；
   去掉 `--dry-run` 落库，页面确认出现；再带 `--merge` 跑一次，确认**不新增行**、进度被刷新。
3. 当晚 23:30 后确认 `daily_schedule.py` 重跑**没删掉** `create_by=-1` 的行，且父表 `remark` 与
   `task_count` 一致。
4. `python3 scripts/check-consistency.py`（无端点/调度变更，应保持绿）。

## 6. 非目标（YAGNI）

- 不做后端 HTTP 接口 / 前端「手工记一笔」按钮（方案 3，过重）。
- 不夜间自动扫 progress 文件（方案 2，把即时记录与定时任务耦合）。
- 不做每模块「最近记录日期」看板（本 spec 先满足范围；需要时另立）。
- 不写 `ingest_batch` / 不注册 dataset。

## 7. 落地清单

- [x] `sql/` 迁移：`sys_user_schedule_task.module`（`spzx-manager/src/main/resources/sql/sys_user_schedule_task_module.sql`，幂等，已应用）
- [x] `spzx-model`：`SysUserScheduleTask.module`
- [x] `scripts/log_work.py`（新建；dry-run/落库/merge/进度文件解析 均已实测）
- [x] `scripts/daily_schedule.py`：`remark` 口径修正（已跑 2026-10-08 验证 −1 行不被删、remark 与 task_count 一致）
- [x] `webstormProject/spzx-admin`：`userSchedule.vue` 模块列/筛选/分组/表单
- [x] 根 `AGENTS.md` + `automation/sourcing/AGENTS.md`：留痕规则
- [ ] 验证：`mvn install -pl spzx-model` + 重启后端（**待无并发 maven / 内存宽裕时执行**；其余验证已过）
