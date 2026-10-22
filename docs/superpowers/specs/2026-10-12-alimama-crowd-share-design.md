# 阿里妈妈「单元×人群」采集 + 推广人群点击占比（2026-10-12）

## 0. 背景与目标

万相台的官方报表只按「关键词 / 计划」聚合，看不到**某个单元的点击里，有多少来自你圈定的人群**。
owner 要的就是这个交叉：某个单元（商品）总点击 10，其中跑在他设的人群上只有 3，
则「推广人群占比 = 30%」——用来判断这个人群值不值得留 / 该不该加溢价。

目标：

1. **只对 #1 关键词标准计划**，把每个单元（=宝贝）的点击拆到它的每个「人群」上，落库、每日采集。
2. 页面按**单元**汇总展示：**推广人群点击量**（Σ该单元各人群 click）、**推广人群占比**（÷ 该单元总 click）。
3. 顺带把其余 3 个重点计划补到**单元级**（含现在被过滤掉的智能 / 控投产计划）。

人群只存明细、不重复造表；展示只在 #1 上出占比。

## 1. 四个重点计划（2026-10-12 实地探明）

| # | 类型 | 计划名 | campaign_id | bidType | 单元数 |
|---|---|---|---|---|---|
| 1 | 关键词推广·标准计划 | 6脉之D标准自选词控点击拉新 | `83392643008` | `custom_bid` | 70 |
| 2 | 关键词推广·日常销售最大化 | 6脉之F自定义智能最大化收割 | `83949710619` | `max_amount` | 71 |
| 3 | 人群推广·标准计划 | 秋冬款标准1 | `83776930735` | `custom_bid` | 20 |
| 4 | 人群推广·收割计划 | 自定义控投产1 | `83340870410` | `roi_control` | 14 |

> 账户「茎肛葫芦娃q」ID 114640889。同一 id 计划改名不改 id（`83392643008` 以前叫「标准计划A」）。
> 关键词推广 = `bizCode=onebpSearch`；人群推广 = `bizCode=onebpDisplay`。
> 标准计划判据仍为 `bidType=custom_bid`；`max_amount` / `roi_control` 是智能 / 控投产。

**为什么占比只做 #1**：#3/#4（人群推广）的计划本体就是拿人群去投，没有「溢价」概念
（探路实测这些人群行 `price.discount=null`），全部流量都算人群，做占比无意义；
只有关键词标准计划里「关键词自然流量 vs 你圈的人群流量」才有区分。

## 2. 接口契约（只读）

### 2.1 计划层 / 单元层（已有，复用）

`collect_alimama_promo.py` 现用：
- 计划层：`POST one.alimama.com/campaign/horizontal/findPage.json`
- 单元（=宝贝）层：`POST one.alimama.com/adgroup/horizontal/findPage.json`，`rptQuery.conditionList[].sourceList=["campaign_detail","adgroup_list"]`

### 2.2 人群层（本次新增，实地跑通）

```
POST https://one.alimama.com/crowd/horizontal/findPage.json?csrfId=<csrf>&bizCode=<onebpSearch|onebpDisplay>
```

请求体（**按计划一次查全部单元**，2026-10-12 实施前实测修正）：

```json
{
  "offset": 0, "pageSize": 500, "orderField": "", "orderBy": "",
  "mx_bizCode": "onebpSearch", "bizCode": "onebpSearch",
  "rptQuery": {
    "fields": "charge,adPv,click,ctr,ecpc,ecpm,alipayInshopAmt,...(同 FIELD_MAP)",
    "conditionList": [{
      "sourceList": ["adgroup_detail", "crowd_list"],
      "startTime": "2026-10-11", "endTime": "2026-10-11", "isRt": false
    }]
  },
  "campaignIdList": ["83392643008"],
  "csrfId": "...", "loginPointId": "..."
}
```

> **不要给 `adgroupIdList`**：实测（2026-10-12，HEAD 版探路）不给它时按 `campaignIdList` 一次返回**该计划全部单元**的
> 人群行——#1 一次回 `count=276`（69 个单元 × 4 人群），与给全 `adgroupIdList` 的结果逐行一致。
> 不给 vs 给全 id：两次都 276 行 / 69 个单元。**按计划的单次查询把请求量从 70/天/计划压到 1/天/计划**
> （滚动 15 天约 1050 次 → 15 次），风控面小一个量级，故采用它。
>
> `sourceList` 必须是 `["adgroup_detail","crowd_list"]`——和单元层一样，它放在 `rptQuery.conditionList` 里；
> 放错位置接口会忽略并回上层汇总（单元层曾踩过同样的坑）。
> 鉴权沿用现有 `borrow_template`：在页面上下文里借一次真实请求的 `csrfId`/`loginPointId`，再重放。

响应 `data.list[]` 每行是一个 **(单元, 人群)**：

| 字段 | 含义 |
|---|---|
| `crowdId` | 人群实例 id（每单元实例化，配合 adgroupId 唯一） |
| `adgroupId` / `campaignId` | 所属单元 / 计划 |
| `onlineStatus` | 1=启用 |
| `crowdInterval` | 人群规模，如 `< 5%` |
| `price.discount` | **人群溢价(%)**，如 300（#1 有，#3/#4 为 null） |
| `crowd.crowdName` | 人群名，如 `受众20261007184658`、`三级女30_34L4` |
| `crowd.crowdValue` | 人群值（达摩盘受众 id） |
| `crowd.label.optionList[].optionDesc` | 定向标签，如 `女` / `25-29岁` / `购买力L4` |
| `reportInfoList[0]` | **该单元×该人群的指标**：charge/adPv/click/ctr/ecpc/alipayInshopAmt/alipayInshopNum/cvr/cartInshopNum/itemColInshopNum/shopColDirNum/colNum/itemColInshopCost…（字段名同 FIELD_MAP；`bpCrowdId`/`crowdType`/`promotionName` 另带） |

`reportInfoList` 为空 = 该人群当天这个单元没有投放数据（与 item 层同口径，**不写 0 行**）。

> 人群行本身**不带 `material`**（拿不到 `material.materialId` = `item_id`）。`item_id` 必须从**单元层**的
> `adgroup/horizontal/findPage.json` 结果按 `adgroupId` join 回来；`adgroupName` 人群行里有（在
> `reportInfoList[0]` 内），但 `item_id` 没有，所以人群采集依赖单元层的 adgroup 列表。

实测规模（2026-10-11）：#1 单次计划级查询回 `count=276`（69 个单元 × 4 人群）；其中带 `charge` 键的仅 5 行
（当天多数单元没在人群上花钱），其余 `reportInfoList` 为空 → 按上面口径跳过。

证据样本：`automation/tb-auto/alimama_promo_raw/crowd_sample_20261012.json`（gitignored）。

## 3. 数据模型 / 落库

**复用 `promo_cost_item_daily`，不新建表。** 该表的 `dimension` 注释本就预留了 `crowd`。

| 列 | 人群行取值 |
|---|---|
| `dimension` | `crowd` |
| `plan_type` | `keyword`（关键词产品线；**不要**用 `crowd`——那表示人群推广产品线，会撞） |
| `entity_key` | `"<adgroupId>:<crowdId>"`（人群实例不含单元 id，复合才唯一） |
| `entity_id` | `crowdId` |
| `entity_name` | `crowd.crowdName` |
| `item_id` / `item_name` | 单元的 `material.materialId` / `adgroupName`（与 item 行同源，可 join 商品） |
| `unit_id` / `unit_name` | `adgroupId` / `adgroupName` |
| `campaign_id` / `campaign_name` | 计划 |
| `report_source` | `alimama-crowd:onebpSearch` |
| `charge/ad_pv/click/ctr_percent/...` | 由 `reportInfoList[0]` 用现有 `FIELD_MAP`/`cast` 映射 |
| `raw_json` | 整行原始值（含 `price`/`crowdInterval`/`crowd.label`，以后要展示溢价时不必重采） |

自然键不变：`(shop_id, dimension, entity_key, campaign_id, stat_date)`，现有 `upsert()` 直接用。

## 4. 采集器改造（`automation/tb-auto/collect_alimama_promo.py`）

1. **`--level` 扩值**：`campaign | item | crowd | both | all`
   - `campaign` = 只采计划日报；`item`/`both` = 计划+单元（这两个现值行为不变，向后兼容）；
   - `crowd` = 计划+单元+人群；`all` = 同上（显式名）。
   - 人群层依赖单元层的 adgroup 列表（见 §2.2 修正），故凡要采人群都必然包含单元层。
2. **人群层 `collect_crowds(page, tpl, biz, campaign_id, day, adgroup_by_id, args)`**：
   - 在单元层之后，**按计划**调一次 `crowd/horizontal/findPage.json`（不给 `adgroupIdList`，`pageSize` 默认 500，
     超 count 再按 `should_page` 翻页）；
   - 取到单元层那次的 adgroup 列表，按 `str(adgroupId)` 建 `adgroup_by_id` 映射，用来补 `item_id`/`item_name`；
     映射里没有的单元（理论上不会）跳过并计数；
   - 新增 `map_crowd_row(crowd_row, adgroup, stat_date, shop_id, plan_type, report_source)`：
     `reportInfoList` 空或无 `charge` → 跳过；否则按 §3 组行、`FIELD_MAP` 映射；
   - 写入走同一个 `upsert(conn, "promo_cost_item_daily", ITEM_COLS, rows, batch_tag)`。
   - `collect_items` 现在要**一并返回扫到的 adgroup 原始列表**（`(rows, seen, pages, adgroups)`），供人群层 join。
3. **人群层只对白名单计划**：`--crowd-campaign-ids`（默认 `83392643008`）。
4. **单元级放开到 #2/#4**：现 `is_standard()` 只收 `custom_bid`。新增 `--include-campaign-ids`
   （默认 `83949710619,83340870410`），这些计划**不论 bidType**也收单元行；其余计划维持只收标准计划。
5. 台账：人群行与单元行同表同批，仍记在 `promo_cost_detail`。若人群层单独失败，在 `end_batch` 的 note 里注明
   （不因此把整批标 failed，人群只是附加维度）。

## 5. 后端读接口（`promo` 域）

给 `PromoItemVo` 增两列，扩 `PromoReportService.items` 的查询：

| 字段 | 含义 |
|---|---|
| `crowdClick` (Long) | 区间内该宝贝各人群 click 之和；无人群数据为 null |
| `crowdClickShare` (BigDecimal) | `crowdClick / click × 100`（百分数，如 `30.00`）；`click=0` 或无数据为 null |

实现：`selectItems` 对 `promo_cost_item_daily` 里 `dimension='crowd'` 的行做聚合（按 `item_id`，
应用同样的 date / plan_type / campaignId / keyword / facet 过滤），LEFT JOIN 到宝贝聚合上；
占比在 service 汇总后算（**先加总再算**，与「比率一律用汇总后的分子分母重算」同纪律），不在 SQL 里逐行除。

`items` 之外（summary/trend/plans/facetCounts）不动。

## 6. 前端展示

「运营 > 推广日报」宝贝页，新增两列：**推广人群点击量**、**推广人群占比**。
- 只有 #1（关键词标准计划）会有值，其余行留空——因为只有 #1 采了人群层。
- 占比直接渲染后端返回的 `crowdClickShare`（百分数），前端不自己算。

## 7. 调度

不新增作业。改 `automation/tb-auto/cron_alimama_promo.sh`（LaunchAgent `com.spzx.alimama-promo`，每日 22:00）：

```
collect_alimama_promo.py --level all --days 15 \
  --crowd-campaign-ids 83392643008 \
  --include-campaign-ids 83949710619,83340870410
```

- 仍窗口模式 9222（脚本注释：headless 易被 RGV587 拦），滚动 15 天靠唯一键 upsert 覆盖归因回补。
- 三处调度对齐（`ingest_dataset.cron_expr` / task-progress 卡片）**不变**（同一作业、同一时刻）。

## 8. 验证 / 一致性

1. **子集校验**：对每个 `(item_id, campaign_id, stat_date)`，Σ人群 click 应 **≤** 单元 click。
   一次性脚本对比 `dimension='crowd'` 与 `dimension='item'`，打印违反项（> 即报警，不静默）。
2. **口径样例**：取一个"单元 10 次点击、人群 3 次"的行，页面占比应为 30%（人工核对）。
3. 人群行的 `item_id` 能 join 上 `platform_product.code`（与 item 层一致）。
4. 单测：`map_crowd_row` 的解析（`reportInfoList` 空跳过、复合 entity_key、指标 cast）；
   `crowdClickShare` 的汇总口径（先加总再除、click=0 出 null）。
5. 跑 `python3 scripts/check-consistency.py` 不引入新漂移。

## 9. 风险 / 未决

- **点击是否重复计数**：一个用户理论上可能命中多个人群。若平台把一票点击记到多个人群，Σ人群 click 会 > 单元 click——
  §8.1 的子集校验就是用来兜这个的；真超了要改成"取最大人群"或改用平台的人群归因口径。
- **人群层归因回补**：成交类指标隔天会变，故人群层也走 15 天滚动重拉 + upsert 覆盖。
- **溢价/规模/标签只进 `raw_json`**：页面暂不展示；以后要展示溢价列再从 raw_json 提或补列。
- **#2（智能计划）的人群行只有 1 条**（"365天无成交店铺潜客"），结构与其他一致，但本次不采（只 #1 采人群层）。

## 10. 不做（Out of scope）

- #2/#3/#4 的人群层采集与展示。
- 人群溢价自动调整（现有 `adjust_alimama_bid.py` 是另一条线，本次不联动）。
- 单独的人群事实表 / 人群维度看板。
