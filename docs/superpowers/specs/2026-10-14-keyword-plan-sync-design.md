# 关键词标准计划搬迁（sync_keyword_plan）设计

> ⚠️ **已作废（2026-10-14）**：用户改为「**重新选词**」而非照搬旧词，本方案不再采用。
> 现行设计见 `2026-10-14-pick-plan-keywords-design.md`。以下内容仅存档。

**日期**：2026-10-14
**状态**：已作废（被 `2026-10-14-pick-plan-keywords-design.md` 取代）
**脚本**：`automation/tb-auto/sync_keyword_plan.py`（新建）

## 1. 背景与目标

用户的关键词推广「标准计划」建错了，要重建。新计划的**商品(单元)**与**分时折扣**都与旧计划一致，
**关键词需要从旧计划同步过去**；但出价不照搬，**按公式重算**。

> 单元（adgroup）由商品决定。旧计划每个商品=一个单元，单元名=商品标题。

**目标**：把旧标准计划各单元的关键词，搬到新标准计划的同名单元；每个词按「手淘市场均价」重算基础出价。

## 2. 口径（与 KwBidCalculator / adjust_alimama_bid.py 一致）

```
关键词出价(基础出价) = 手淘市场均价 / ((1 + 人群溢价%) × 分时折扣%)
```
- 参数固定值：`--premium`（默认 300）、`--discount`（默认 35）→ 默认除以 1.4；全能调价未开不计。
- 向下取到分（`money_floor2`，先修浮点毛刺再 FLOOR）；低于 `--min-bid`（默认 0.05）抬到 min-bid。
- 查不到「手淘」行 / 无市场均价 → 记 `skip_no_market` 跳过，**不猜**。

## 3. 组件与数据流

复用现有件，不重写：
- 单元枚举：`adjust_alimama_bid.open_units_page`（重放 `adgroup/horizontal/findPage.json`，pageSize=200，含暂停单元）。
- 单单元读词：`adjust_alimama_bid.goto_unit`（`.../manage/search-detail?...&tab=&adgroupId=` → `tr.keyword-item`）；
  需**扩展** `READ_KEYWORDS_JS` 同时读该词的**匹配方式**（旧词 matchScope）。
- 市场均价：`adjust_alimama_bid.market_avg`（流量解析页「竞争流量透视」→ 核心流量来源=手淘行 的 ￥ 值）。
- 出价计算：`adjust_alimama_bid.calc_bid` / `money_floor2`。
- 写入：`add_alimama_keywords.py` 的 `POST /bidword/add.json`
  payload `{campaignId, adgroupId, word, bidPrice, matchScope, recReason:None}`；
  `csrfId`/`loginPointId` 从页面请求现取（会话级）。

流程：
1. 连 9222 窗口模式（万相台已登录）。
2. 枚举**旧计划**单元 → 逐单元读关键词 `[{word, matchScope, href(流量解析)}]`。
3. 枚举**新计划**单元 → `标题 → adgroupId` 映射；标题对不上的旧单元 → 记 `skip_no_unit` 列清单**待人工**（不猜）。
4. 逐词：`market_avg(href)` → `calc_bid` → `add.json` 写入新计划对应单元（带算出出价 + 旧词匹配方式）。
5. 报告 json 断点/幂等：按 `(toAdgroupId, word)` 就地更新；默认续跑跳过 `ok`。

## 4. CLI

```
automation/venv/bin/python tb-auto/sync_keyword_plan.py \
  --from-campaign <旧id> --to-campaign <新id> \
  --premium 300 --discount 35 --source 手淘 --min-bid 0.05 \
  --gap 4 --limit 0 --report sync_keyword_report.json [--dry-run|--apply]
```
- 默认 `--dry-run`：只读+打印「单元 → 搬N词 / 跳过N(无均价) / 出价 min~max」，不写。
- 只有 `--apply` 才写。写入异常（`no_dialog`/风控迹象）→ 停本轮保留现场。

## 5. 默认假设（不同意需改）

1. 匹配方式（广泛/精确）照搬旧词。
2. 只搬旧计划**启用中**的词；暂停词不搬。
3. 出价一律按公式重算，不照搬旧价（用户已确认）。
4. 单元按**标题**匹配；标题改了/商品不在新计划 → `skip_no_unit` 待人工。

## 6. 边界与失败处理

- 新计划尚未创建 → 本脚本可先写完；**dry-run 验证需等新计划 campaign-id**。
- `skip_no_market`：市场均价取不到（弱词/新词）→ 跳过并在报告列出，人工补。
- 标题重名：旧计划多个单元同名 → 只要新计划对应标题唯一即无歧义；不唯一则记 `ambiguous` 待人工。
- 匹配方式读不到（行内无该列文本）：记 `match_unknown` 并入报告，按**人工确认**而非默认广泛写入（避免把精确词写成广泛）。
- 断点：报告 json 是唯一状态；要重跑某单元先删其 items。
- 已知坑（AGENTS 已记）：搜索详情页 URL 的 `tab=` 必须为空；流量解析页 hash 路由须 `about:blank` 再 goto；
  csrfId 缺失直连报 `2102001`。

## 7. 验证

- dry-run 打印与旧计划页面逐单元比对（词数、匹配方式、出价范围）。
- apply 后抽 2-3 个单元，在新计划页面核对词与出价、匹配方式。
- 与 `adjust_alimama_bid.py` 同口径：同一词当天重算结果应与直接调价一致。

## 8. 未决

- 新计划 campaign-id（待用户创建）。
- 人群溢价/分时折扣确认值（默认 300/35）。
- 是否需要把旧计划旧词一并删除（用户说旧计划"重新建"，删除旧计划本身由用户操作，不在本脚本范围）。
