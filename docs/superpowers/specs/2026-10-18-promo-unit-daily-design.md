# 万相台标准计划「单元日报」：关键词明细 + 人群点击占比下钻（2026-10-18）

## 0. 背景与目标

计划 `84290744044`（关键词推广·标准计划，custom_bid，67 单元 463 词，2026-10-17 刚做过 reprice 调价）
是 owner 当前的优化重点，计划的目的是**提升人群资产占比**。现在后台只有计划级/宝贝级汇总
（推广日报页），看不到：

1. 每个单元（=宝贝）**每天**的关键词明细（点击量、均价、收藏、加购、成交单数、成交金额、ROI）；
2. 每个单元**每天**的人群点击量，以及**人群点击占比**（人群命中点击 ÷ 单元总点击，差额=泛流量）；
3. 上述各维度随时间的变化（reprice 前后对比）。

目标：**只对 84290744044**（白名单制，以后加计划再加白名单）打通单元级词层采集 + 新页面「推广·单元日报」。

前置设计：`2026-10-12-alimama-crowd-share-design.md`（人群层已实施跑通：crowd 接口按计划一次回全部
单元人群行、`promo_cost_item_daily.dimension='crowd'` 落库、推广日报宝贝页占比列雏形）。本设计在其上
补**词层**与**单元视角展示**，占比口径与其完全一致（先加总再除、分母 0 出 NULL）。

## 1. 范围

| 层 | 现状 | 本次动作 |
|---|---|---|
| 计划层 | 已通 | 不动 |
| 单元层 | 已通（`is_standard()` 收 custom_bid，84290744044 自动覆盖） | 不动 |
| 人群层 | 已通，白名单 `--crowd-campaign-ids 83392643008` | 白名单扩入 84290744044 |
| **词层** | **0 行，接口未证实**（前两轮探针失败史见 §2） | **新探针 + 新采集层（本设计核心）** |

## 2. 词级接口（唯一未证实点，探针先行）

**失败史**（不要重复走这两条路）：

- `report/query.json` + `tab=word` 类参数 → 只回计划汇总行；
- `probe_alimama_item_tab.py` 监听 search-detail 页 XHR → 只抓到 `component/findList.json`（页面组件配置，非报表）。

**新探针 `probe_alimama_word_tab.py`**：

- 用 `add_alimama_keywords.py` 验证过的单元详情页 URL 形态打开 84290744044 的一个单元（CDP 9222，页面停在 one.alimama.com）；
- `page.on("response")` 监听所有 `.json` XHR，脚本内切【关键词】tab（tab 参数必须为空后再点页面元素，同 `add_alimama_keywords.py` 先例）、再切【人群】tab 核对；
- 产物：词级报表请求模板（url/body/字段形态）落 `probe_alimama_out/`（gitignored），人工确认字段后写进本节的实施记录。

**预期形态**（待证实）：与 crowd 层同构——

```
POST https://one.alimama.com/<word-path>/horizontal/findPage.json?csrfId=...&bizCode=onebpSearch
rptQuery.conditionList[].sourceList = ["adgroup_detail", "word_list"]   # sourceList 必须在 conditionList 里！
campaignIdList = ["84290744044"]
```

> `sourceList` 放顶层会被忽略并回上层汇总——单元层、人群层都踩过的同一个坑（10-12 设计 §2.2）。
> 若不给 `adgroupIdList` 一次回全计划词行（像人群层 276 行）→ 1 发/天/计划；若必须逐单元 →
> 67 发/天/计划（可接受，探针定）。

**粒度假设**：词 tab 挂在单元详情页下 → 数据应为「词 × 单元」粒度（这正是本设计要的）。若探针发现平台
只给计划级词报表（无法挂到单元），词层降级为 §9.1 的退路。

**DOM 兜底（仅降级用）**：`adjust_alimama_bid.py` 已证词行在流量解析页 DOM 可见（`#bidword_<id>_price`），
但只能抓当日、不可回补——不作主路。

### 2.1 实施记录（2026-10-19 探针实测）

探针 `probe_alimama_word_tab.py`（8:16 实测，142 个响应）+ 补抓 request（`/tmp/word_findList_req.json`）：

- **URL**：`POST https://one.alimama.com/bidword/findList.json?csrfId=...&bizCode=onebpSearch`
  ——**不是**预期的 `bidword/horizontal/findPage.json`。
- **请求体**（页面原样，带报表的那个）：
  ```json
  {"offset": 0, "pageSize": 40, "queryType": "0", "mx_bizCode": "onebpSearch", "bizCode": "onebpSearch",
   "rptQuery": {"fields": "avgRank,adPv,click,ctr,charge,ecpc,cartInshopNum,itemColInshopNum,ecpm,alipayInshopAmt,cartRate,itemColInshopCost",
                 "conditionList": [{"sourceList": ["adgroup_detail", "bidword_list"],
                                    "adzonePkgIdList": ["114790550288", "114786650498"],
                                    "startTime": "2026-10-19", "endTime": "2026-10-19", "isRt": true}]},
   "campaignIdList": ["84290744044"], "adgroupIdList": ["84290656281"],
   "csrfId": "...", "loginPointId": "..."}
  ```
  - `sourceList = ["adgroup_detail", "bidword_list"]`（**bidword_list**，非预期的 word_list）——仍在 conditionList 里，坑位与 crowd 层一致。
  - **`adgroupIdList` 必须给**（2026-10-19 dry-run 实测：不给直接报 `adgroupIdList不能为空`，与 crowd 层「不给回全计划」相反）→ 词层**逐单元采集**：对当天有投放的单元（`reportInfoList[0]` 含 charge 键，与单元行同判据）各发一次，`pageSize=500` 一页回该单元全部词；昨天 49/67 单元有数 ≈ 49 发/天，可接受。
  - `adzonePkgIdList` 是页面 echo 的推广位过滤，采集器不传（实测不传可正常返回词行）。
  - 历史日期 `isRt: false`（页面当天实时才是 true）。
  - fields：采集器用全量 FIELDS_STR（32 项，与 crowd 层同策略）试，页面原样只给 12 项；dry-run 验证服务端接受度，拒绝则退页面 12 项 + 单测同步。
- **响应**：`data.list[]` 每行 `bidwordId/word/adgroupId/campaignId/matchScope/bidPrice/reportInfoList/reportInfoMap/...`
  ——**行自带 adgroupId**（归属单元直接有，不用从单元层猜）。`reportInfoList[0]` 字段与 FIELD_MAP 对上
  （charge/adPv/click/ctr/ecpm/alipayInshopAmt/cartInshopNum/itemColInshopNum/alipayDirAmt/alipayIndirAmt/...）；
  `reportInfoList: null` = 该词当天无投放（与 item/crowd 同口径，跳过）。
  样本：`resp_132.json`（70 词无报表）/ `resp_134.json`（70 词中 10 行有报表，condition 回显 startTime/endTime）。
  `count=70` 是单单元词数；计划 463 独立词分布在 67 单元。

## 3. 数据模型（复用 `promo_cost_item_daily`，不新建表）

| 列 | 词行取值 |
|---|---|
| `dimension` | `keyword`（表注释本就预留） |
| `plan_type` | `keyword`（onebpSearch 产品线） |
| `entity_key` | **`"<adgroupId>:<keywordText>"` 复合** —— ⚠️ 同一个词会被多个单元共用（计划级词库），光用词文本做 key 会让两个单元的同名词行在唯一键 `(shop_id, dimension, entity_key, campaign_id, stat_date)` 上互踩、upsert 互相覆盖。复合模式对齐 crowd 行的 `<adgroupId>:<crowdId>`（10-12 设计 §3） |
| `entity_id` | 平台词 id（有则存，无则空——10-12 设计已注明「关键词没有 id，用词本身」，探针确认） |
| `entity_name` | 关键词文本 |
| `unit_id` / `unit_name` | `adgroupId` / `adgroupName` |
| `item_id` / `item_name` | 从单元层 adgroup 列表按 adgroupId join 回来（同 crowd 层做法） |
| `campaign_id` / `campaign_name` | 84290744044 |
| `report_source` | `alimama-keyword:onebpSearch`（命名对齐 `alimama-crowd:onebpSearch`） |
| `charge/click/cpc_percent/colNum/cartInshopNum/alipayInshopNum/alipayInshopAmt/roi/...` | `FIELD_MAP` 现有 31 字段映射（点击/均价/收藏/加购/成交单数/成交金额/ROI 全覆盖） |
| `raw_json` | 整行原始值 |

自然键与 `upsert()` 不变。**人群占比不落库**——查询现算（与「不存派生值」纪律一致）。

数据量：463 词摊 67 单元，估 400-500 词行/天；15 天滚动 ≈ 7000 行；30 天回补 ≈ 1.5 万行，很轻。

## 4. 采集器改造（`automation/tb-auto/collect_alimama_promo.py`）

1. **`--level all` 语义扩展**：`all` = 计划+单元+人群+**词**（词层只对白名单内计划采，白名单为空的
   计划零词行，向后兼容）；新增显式值 `word` 便于单测/手动补采。现值 `campaign|item|crowd|both` 行为不变。
2. **`--word-campaign-ids`**（默认 `84290744044`）：词层白名单。
3. **`--crowd-campaign-ids`** 采集器默认值**不动**（仍 `83392643008`）；扩入 84290744044 只发生在 §7 的
   cron 命令行上——命令行是唯一真相，不在默认值里再存一份。
4. **`collect_words(page, tpl, biz, campaign_id, day, adgroup_by_id, args)`**：
   - 按 §2 探针模板逐日拉词行；超 count 按 `should_page` 翻页（同 crowd 层）；
   - `map_word_row(word_row, adgroup, stat_date, shop_id, plan_type, report_source)`：
     `reportInfoList` 空/无 charge → 跳过（同 item/crowd 口径，不写 0 行）；
   - 写入走同一 `upsert(conn, "promo_cost_item_daily", ITEM_COLS, rows, batch_tag)`。
5. **台账并入 `promo_cost_detail`**（不新增 dataset）：避免动注册表/`cron_alert`/看板卡片/四副本对齐那串
   连锁。词层单独失败 → `end_batch` note 注明，不把整批标 failed（同 crowd 层先例）。
6. **滚动重拉 15 天** + upsert（成交归因回补）；首采手动 `--days 30` 回补一次。

## 5. 后端读接口（`promo` 域，新 `PromoUnitController`，纯只读）

| 接口 | 作用 |
|---|---|
| `GET /admin/promo/unit/units?campaignId&from&to` | 单元列表：花费/点击/均价/收藏/加购/成交单数/成交额/ROI + `crowdClick`/`crowdShare`（占比现算：该单元 `dimension='crowd'` 行点击合计 ÷ `dimension='item'` 行点击） |
| `GET /admin/promo/unit/trend?campaignId&unitId&from&to` | 单元逐日全指标（含占比逐日值，前端勾选画线） |
| `GET /admin/promo/unit/keywords?campaignId&unitId&from&to` | 词明细（词/点击/均价/花费/收藏/加购/成交单数/成交金额/ROI），可排序 |
| `GET /admin/promo/unit/crowds?campaignId&unitId&from&to` | 人群明细（人群名/点击/花费/占比） |

- 计划下拉复用现有 `GET /admin/promo/report/plans`。
- 占比计算纪律与 10-12 设计一致：**先加总再除**（不在 SQL 逐行除）、分母 0 出 NULL。
- 与现有 items 接口 `crowdClickShare` 的关系：同口径不同视角（本处按 `unit_id`=adgroupId 聚合，过滤维度
  是 campaign+unit、不带宝贝页的 facet/keyword 过滤），各自独立 SQL，不互相依赖。
- 已知坑：`promo_cost_item_daily`(general_ci) join `promo_plan`(0900_ai_ci) 显式 COLLATE。
- 新增端点必须过 `check-consistency.py` 前后端路由对齐门（前端 api 文件同步加）。

## 6. 前端（新页面 `promoUnit.vue`，路由 `/promoUnit`，「运营」菜单、推广日报旁边）

不动现有推广日报页。布局自上而下：

1. **工具栏**：计划下拉（默认 84290744044）+ 日期区间（默认近 14 天）。
2. **单元列表**：单元名/花费/点击/均价/收藏/加购/成交单数/成交额/ROI/**人群占比**，可排序。
   占比列是主角：低于阈值（初始 80%，前端常量可调）的行着色醒目；tooltip 写清口径
   （「人群命中点击 ÷ 单元总点击，差额 = 泛流量」，差额在 tooltip 里明示，不粉饰）。
3. **点行展开单元详情**：
   - 趋势图（echarts）：维度勾选器（点击/花费/成交额/ROI/收藏/加购/人群占比），默认勾点击+花费；
   - 关键词明细表 / 人群明细表，两个 tab 切换。
4. **优雅降级**：词层未采到数据时词表显示「词级明细待采集」占位，不报错（探针失败退路时不阻塞页面上线）。

## 7. 调度

只改一行：`automation/tb-auto/cron_alimama_promo.sh`（LaunchAgent `com.spzx.alimama-promo`，每日 22:00，
窗口模式 9222）命令追加：

```
--crowd-campaign-ids 83392643008,84290744044 --word-campaign-ids 84290744044
```

`--level all` 语义扩展后其余参数不变。无新 cron、无新 dataset、无新看板卡片，三处调度对齐不动。

## 8. 验证

1. **词行子集校验**：对每个 `(unit_id, campaign_id, stat_date)`，Σ词 click 应 ≈ 单元 click
   （关键词流量应占单元绝大部分）；一次性脚本对比 `dimension='keyword'` vs `dimension='item'`，
   偏差打印人工看（不静默）。人群行维持 10-12 设计 §8.1 的 ≤ 校验。
2. **entity_key 复合唯一性单测**：同词双单元两行 upsert 后都还在，不互踩。
3. `map_word_row` 单测：空 `reportInfoList` 跳过、复合 entity_key、指标 cast（仿 `test_alimama_map.py` 风格）。
4. 后端占比单测：先加总再除、分母 0 出 NULL（纯 JUnit，不拉 Spring）。
5. `python3 scripts/check-consistency.py` 无新漂移（新增 4 端点前后端同步）。
6. 页面人工验收：84290744044 选 10-17 前后各几天，能看到 reprice 前后各维度变化；
   占比口径抽一行人工核对（10-12 设计 §8.2 同款）。

## 9. 风险 / 未决

1. **词级接口形态未证实（最大不确定）**。退路链：DOM 抓词行（仅当日、不可回补）→ 降级先上
   「单元+人群」两层（人群层零不确定，页面 §6.4 已留占位）。探针是第一个实施步骤，结果回填 §2。
2. **9222 时段**：探针与 30 天回补都在 9222 页面上下文跑——白天手动做，避开 19:30 ISV 轮与
   22:00 采集窗口；9222 同时挂着建档补跑时先协调。
3. **词行拉取量**：全计划 1 发 vs 逐单元 67 发，探针定（均可接受）。
4. **人群行点击合计 ≠ 单元点击**（差额=泛流量，这正是占比的意义）——界面明示差额。
5. **词报表粒度**：若平台只给计划级词报表（挂不到单元），词层按 §9.1 退路降级。

## 10. 不做（Out of scope）

- 其他计划的词层采集（白名单制，以后要再加）。
- 词级自动出价调整（`adjust_alimama_bid.py` 是另一条线，不联动）。
- 词 × 人群交叉粒度（平台大概率没有）。
- 占比/汇总落库或物化（查询现算）。
- 推广日报现有页面的改动。
