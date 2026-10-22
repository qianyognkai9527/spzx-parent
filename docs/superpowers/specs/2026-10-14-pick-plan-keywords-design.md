# 新标准计划选词 + 算出价（pick_plan_keywords）设计

**日期**：2026-10-14
**状态**：已实现（dry-run 冒烟通过；`--apply` 待用户建好新计划、提供 campaign-id 与溢价/折扣后实跑）
**脚本**：`automation/tb-auto/pick_plan_keywords.py`（已建）
**取代**：`2026-10-14-keyword-plan-sync-design.md`（原「照搬旧词」方案已作废）

## 1. 背景与目标

用户的关键词推广「标准计划」建错了，要重建。新计划的**商品(单元)**与**分时折扣**由用户在页面上自行选好（单元由商品决定，单元名=商品标题）。

新计划的关键词**不从旧计划照搬**，而是**重新选**：按平台推荐候选 + 标题派生约束筛词，再对每个词查手淘市场均价、按公式算出基础出价，写入新计划对应单元。

> 「按标题选词」是误述——词来自**平台推荐**，标题只作**过滤约束**。

**目标**：给新标准计划每个单元自动化「选词 → 查均价 → 算价 → 写入（广泛匹配）」一条龙。

## 2. 口径

### 2.1 出价公式（与 `KwBidCalculator` / `adjust_alimama_bid.py` 一致）

```
关键词出价(基础出价) = 手淘市场均价 / ((1 + 人群溢价%) × 分时折扣%)
```
- `--premium`（默认 300）、`--discount`（默认 35）→ 默认除以 1.4；全能调价未开不计。
- 向下取到分（`money_floor2`：先修浮点毛刺再 FLOOR）；低于 `--min-bid`（默认 0.05）抬到 min-bid。
- 查不到「手淘」行 / 无市场均价 → 记 `skip_no_market`，**不写、不猜**，列清单人工补。

### 2.2 选词（完全复用 `add_alimama_keywords.py` 逻辑）

候选来源（平台推荐接口 `POST /bidword/suggest/kr/list.json`）：
- AI选词 `kr_fill_by_item`（抽屉默认 tab）
- 趋势机会词 `kr_new_mta`（关键词推荐 → 趋势机会词）

过滤/排序：
1. 搜索指数 ≥ `--min-index`（默认 1000）；该来源一个都选不出时放宽到 `--min-index-fallback`（默认 200）再选一次。
2. 长度 ≥ 2；不含虚词 `的/了/吗/呢/吧`。
3. 必须含**标题所属品类家族**名词（`GARMENT_FAMILIES`：外套/大衣/皮草/毛衣/裙/裤/套装…），且**不得**落进别的家族。
4. 标题声明的领型/长度维度，命中**同维度不同值**即剔（`COLLARS`/`LENGTHS`）。
5. 可选材质维度（`--material-filter`），默认关。
6. 排序：搜索指数降序（并列次键 市场点击率→市场点击转化率），取前 `--top`。
7. 对单元**已有词**、以及本轮两来源之间去重（`norm`=去空白）。

### 2.3 匹配方式

**全部广泛匹配**，用页面默认值 `matchScope=4`（用户确认：默认即广泛）。不做逐词匹配方式选择。

## 3. 组件与数据流

复用现有件，不重写：

| 复用 | 来源 |
|---|---|
| 单元枚举 `get_units`/`open_units_page`（`adgroup/horizontal/findPage.json` pageSize=200，含暂停） | `add_alimama_keywords.py` / `adjust_alimama_bid.py` |
| 单元页 + 加词抽屉 + 双来源候选捕获（`open_drawer`/`click_tab`/`click_sub`/`kr/list.json` 响应嗅探） | `add_alimama_keywords.py` |
| 选词 `select_words`/`is_relevant`/`_pick_with_fallback` + 词典 `GARMENT_FAMILIES`/`COLLARS`/`LENGTHS`/`BAD_CHARS` | `add_alimama_keywords.py` |
| 手淘市场均价 `market_avg` + `READ_MARKET_JS` + 流量解析页 | `adjust_alimama_bid.py` |
| 出价 `calc_bid`/`money_floor2` | `adjust_alimama_bid.py` |
| 写入模式 `POST /bidword/add.json`（`csrfId`/`loginPointId` 页面现取） | `add_alimama_keywords.py`（**参考其 payload，新脚本自己写带 per-word `bidPrice` 的 add**） |

> 复用方式：`import` 两模块的**纯函数/常量**（`select_words`/`is_relevant`/词典、`calc_bid`/`money_floor2`/`market_avg`/`READ_MARKET_JS`、`get_units`/`open_drawer`/`click_tab`/`click_sub`），**新脚本自己写编排与写入**。
> **不改 `add_alimama_keywords.py` / `adjust_alimama_bid.py` 的现有行为**（那两个脚本在生产里跑，改了有回归风险）；公式/词典只此一份，不复制。

流程：
1. 连 9222 窗口模式（万相台已登录）。
2. 枚举**新计划**单元 → `标题 → adgroupId`。
3. 逐单元：进单元页 → 开抽屉 → 捕获两来源候选 → 选词（去重已有词）。
4. 逐入选词：拼流量解析 URL（**用词**，不依赖 bidwordId）→ 读「手淘」均价 → `calc_bid`。
5. 有价者 `POST /bidword/add.json` 写入（广泛 + 算出价）；无价者记 `skip_no_market`。
6. 报告 json 断点/幂等：按 `(adgroupId, word)` 就地更新；默认续跑跳过 `ok`。

## 4. CLI

```
automation/venv/bin/python tb-auto/pick_plan_keywords.py \
  --campaign-id <新id> \
  --premium 300 --discount 35 --source 手淘 --min-bid 0.05 \
  --min-index 1000 --min-index-fallback 200 --top 30 \
  --match-scope 4 --gap 4 --limit-units 0 \
  --report pick_keywords_report.json [--dry-run|--apply]
```
- 默认 `--dry-run`：只读+打印「单元 → 入选N词 / 有价N / skip_no_market N / 出价 min~max / 均价范围」，不写。
- 只有 `--apply` 才写。写入异常（`no_dialog`/风控迹象）→ 停本轮保留现场。
- `--adgroup-id` 可只跑指定单元；`--limit-units` 限量试点。

## 5. 默认假设（不同意需改）

1. 匹配方式全部**广泛**（`matchScope=4`）。
2. 新计划单元标题=商品标题，与推荐接口按单元取候选一致。
3. 新计划初始**无旧词**；若已有词则纳入去重（不删）。
4. 两个来源都用，互相去重。
5. 出价一律按公式重算，不照搬任何旧价。
6. `--top 30`（用户定；后续要做关键词汰换，先多铺一点）。

## 6. 边界与失败处理

- `skip_no_market`：均价取不到（弱词/新词）→ 跳过并列清单，人工补。
- 单元页无加词抽屉 / 无推荐 tab（新主线 UI 与智能计划不同）→ 记 `no_drawer` 停该单元，dry-run 先暴露。
- 均价链路连续失败（连续 8 次取不到）→ 疑似登录态/风控，停本轮退出码 4（沿用 `adjust_alimama_bid.py`）。
- 写入异常 → 退出码 3 停并保留报告。
- 断点：报告 json 是唯一状态；重跑某单元先删其 `(adgroupId)` 记录或加 `--force`。
- 已知坑：流量解析页 hash 路由须先 `about:blank` 再 goto；搜索详情页 `tab=` 必须为空；`csrfId` 缺失直报 `2102001`。

## 7. 性能

- 均价**逐词查**（约 5s/词），脚本内**按词缓存**（同词跨单元不重复查）。
- `--top 30` × 2 来源，去重后每单元可能几十词；单元多时为小时级后台长跑，正常。
- 可先 `--limit-units 2` 试点看节奏。

## 8. 验证

- dry-run：与新计划页面逐单元比对入选词、出价范围、skip 清单。
- apply：抽 2-3 个单元，在新计划页面核对词、匹配方式(广泛)、出价。
- 同口径：同一词当天重算，`calc_bid` 结果应与 `adjust_alimama_bid.py` 直接调价一致。
- 复用函数不动 `add_alimama_keywords.py` 原有行为；不新增单测时至少保证两个旧脚本单跑不回归。

## 9. 未决

- 新计划 campaign-id（待用户创建）。
- 人群溢价/分时折扣实际值（默认 300/35，用户建好计划后传参覆盖）。
- 是否把旧计划旧词删除：旧计划本身由用户处理，不在本脚本范围。
- 新标准计划的推荐抽屉 tab 是否与智能计划完全一致（dry-run 首轮确认）。
