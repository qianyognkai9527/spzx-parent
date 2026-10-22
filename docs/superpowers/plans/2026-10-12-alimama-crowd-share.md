# 阿里妈妈「单元×人群」采集 + 推广人群点击占比 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 采集关键词标准计划（#1 `83392643008`）每个单元的人群层点击，落 `promo_cost_item_daily`（`dimension='crowd'`），并在「推广日报」宝贝页显示「推广人群点击量 / 占比」，同时把 #2/#4 两个非标准计划补到单元级。

**Architecture:** Python 采集器（`automation/tb-auto/collect_alimama_promo.py`）在单元层之后，对白名单计划按**计划级单次查询** `crowd/horizontal/findPage.json`（不给 `adgroupIdList`）拿回该计划全部 (单元,人群) 行，用单元层抓到的 adgroup 列表按 `adgroupId` join 出 `item_id`，写进现有明细表（不建新表）。后端 `PromoReportService.items` 的 SQL 增一个按 `item_id` 聚合 `dimension='crowd'` 点击的 LEFT JOIN，占比在 Java 侧先加总再算。前端加两列只渲染后端返回的百分数。

**Tech Stack:** Python 3.9（Playwright async + CDP + pymysql，venv `automation/venv`）、Spring Boot 3.3.5 / MyBatis XML / Java 21、Vue 3 + Element Plus。

## Global Constraints

- Python 一律用 `automation/venv/bin/python`（3.9，全生态共用），不从系统 python3 跑 tm auto 脚本。
- 采集器 `plan_type` 常量：`keyword`（关键词产品线）、`crowd`（人群推广产品线）——**人群行的 `plan_type` 必须是 `keyword`，不是 `crowd`**（那是产品线名，会撞）。
- 人群行：`dimension='crowd'`、`entity_key="<adgroupId>:<crowdId>"`、`entity_id=crowdId`、`entity_name=crowd.crowdName`、`report_source="alimama-crowd:onebpSearch"`。
- 自然键不变：`(shop_id, dimension, entity_key, campaign_id, stat_date)`，复用现有 `upsert()` 与 `ITEM_COLS`。
- `reportInfoList` 为空 / 无 `charge` 键 = 当天没投放数据 → **不写 0 行**（与 item 层同口径）。
- 比率口径：先加总分子分母再相除，绝不做 AVG。
- 后端读接口只在 `items` 上扩；`summary/trend/plans/facetCounts` 不动。
- **不要提交任何改动**（除非用户明确要求 commit）。本计划每一步都不含 git commit。
- 改 `spzx-model`（VO 加字段）后必须 `mvn install -pl spzx-model` 并**完整重启后端**（devtools 只重载 target/classes，model 是 jar）。
- Java 构建用 IDEA 内置 Maven：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`。
- 命令行连库只用 `mysql --defaults-extra-file=/tmp/spzx_my.cnf`（丢了先 `python3 scripts/mysql-cnf.py` 重建）。
- 9222 运维红线：采集类可用 headless；写类必须窗口模式；不与其它 1688/淘宝任务并行。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `automation/tb-auto/collect_alimama_promo.py` | 修改 | 加人群层采集 + 单元级放开白名单计划 |
| `automation/tb-auto/test_alimama_map.py` | 修改 | 纯函数自检（含人群行映射/请求体/level 门） |
| `automation/tb-auto/cron_alimama_promo.sh` | 修改 | 每日 22:00 作业切到 `--level all` + 新 flag |
| `automation/tb-auto/check_crowd_subset.py` | 新建 | 子集校验：Σ人群 click ≤ 单元 click |
| `spzx-model/.../vo/promo/PromoItemVo.java` | 修改 | 加 `crowdClick` / `crowdClickShare` |
| `spzx-manager/.../service/promo/PromoReportService.java` | 修改 | `applyCrowdShare` 纯函数 + items() 接线 |
| `spzx-manager/.../mapper/PromoReportMapper.xml` | 修改 | `selectItems` 增人群聚合 LEFT JOIN |
| `spzx-manager/src/test/.../promo/PromoReportServiceTest.java` | 修改 | 占比口径单测 |
| `webstormProject/spzx-admin/src/views/mall/promoReport.vue` | 修改 | 宝贝页加两列 |

---

### Task 1: 人群行映射 + 请求体 + level 门（纯函数，TDD）

**Files:**
- Modify: `automation/tb-auto/collect_alimama_promo.py`
- Test: `automation/tb-auto/test_alimama_map.py`

**Interfaces:**
- Produces:
  - `map_crowd_row(crowd_row, adgroup, stat_date, shop_id, plan_type, report_source) -> (row|None, reason|None)`
  - `crowd_body(tpl, biz_code, campaign_id, day, offset, page_size) -> dict`
  - `wants_item(level) -> bool`、`wants_crowd(level) -> bool`
  - 常量 `CROWD_URL = "https://one.alimama.com/crowd/horizontal/findPage.json"`

- [ ] **Step 1: 写失败测试** — 在 `test_alimama_map.py` 的 import 里加 `map_crowd_row, crowd_body, wants_item, wants_crowd`，并在文件末尾 `print(...)` 之前追加：

```python
# ---- 人群层: 一个 (单元,人群) 节点 → 一行 promo_cost_item_daily ----
CROWD_INFO = {"charge": 9.81, "adPv": 100.0, "click": 3.0, "ctr": 0.03, "ecpc": 3.27,
              "ecpm": 98.1, "alipayInshopAmt": 0.0, "alipayInshopNum": 0.0,
              "cartInshopNum": 1.0, "itemColInshopNum": 0.0, "shopColDirNum": 0.0,
              "colNum": 0.0, "itemColCart": 0.0, "addNewUv": 0,
              "adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
              "crowdName": "三级女30_34L4"}
CROWD_ROW = {"adgroupId": 83440680802, "campaignId": 83392643008, "crowdId": 29063497481,
             "onlineStatus": 1, "crowdInterval": "< 5%", "price": {"discount": 300},
             "crowd": {"crowdName": "三级女30_34L4", "crowdValue": "108087233",
                       "label": {"optionList": [{"optionDesc": "30-34岁"}]}},
             "reportInfoList": [CROWD_INFO]}
CADG = {"adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
        "campaignId": 83392643008, "campaignName": "6脉之D标准自选词控点击拉新",
        "material": {"materialId": 1072639258886}}

crow, creason = map_crowd_row(CROWD_ROW, CADG, "2026-10-11", 1, "keyword",
                              "alimama-crowd:onebpSearch")
assert creason is None and crow is not None
assert crow["dimension"] == "crowd"
assert crow["plan_type"] == "keyword"                 # 不是 'crowd'(那是产品线名)
assert crow["entity_key"] == "83440680802:29063497481"  # 复合键, crowdId 单用不唯一
assert crow["entity_id"] == "29063497481"
assert crow["entity_name"] == "三级女30_34L4"
assert crow["item_id"] == "1072639258886"             # item_id 来自单元(material)
assert crow["item_name"] == CADG["adgroupName"]
assert crow["unit_id"] == "83440680802"
assert crow["campaign_id"] == "83392643008"
assert crow["report_source"] == "alimama-crowd:onebpSearch"
assert crow["charge"] == 9.81 and crow["click"] == 3 and crow["ad_pv"] == 100
assert crow["ctr_percent"] == 3.0
assert crow["raw_json"].find("crowdInterval") >= 0 and crow["raw_json"].find("discount") >= 0

# reportInfoList 空 / 没有 charge 键 → 当天该人群没投放数据, 不写 0 行
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": None},
                     CADG, "d", 1, "keyword", "s")[1] == "no_data"
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": [{"roi7d": 0}]},
                     CADG, "d", 1, "keyword", "s")[1] == "no_data"
# 缺 crowdId(复合键少一半) → 跳过
assert map_crowd_row({"adgroupId": 1, "reportInfoList": [CROWD_INFO]},
                     CADG, "d", 1, "keyword", "s")[1] == "no_crowd_id"
# 计划 id 在 crowd 行与 adgroup 上都没有 → 跳过
BARE = {"adgroupId": 1, "adgroupName": "x", "material": {"materialId": 111}}
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": [CROWD_INFO]},
                     BARE, "d", 1, "keyword", "s")[1] == "no_campaign"
# 单元连 item_id 都拿不到 → 跳过
assert map_crowd_row(CROWD_ROW, {"adgroupName": "x"},
                     "d", 1, "keyword", "s")[1] == "no_item_id"

# ---- 人群请求体: sourceList 必须在 rptQuery.conditionList 里, 且不给 adgroupIdList ----
cb = crowd_body({"body": {"csrfId": "C", "loginPointId": "L"}},
                "onebpSearch", 83392643008, "2026-10-11", 0, 500)
assert cb["rptQuery"]["conditionList"][0]["sourceList"] == ["adgroup_detail", "crowd_list"]
assert "adgroupIdList" not in cb
assert cb["campaignIdList"] == ["83392643008"]
assert cb["csrfId"] == "C" and cb["loginPointId"] == "L"
assert cb["rptQuery"]["conditionList"][0]["isRt"] is False

# ---- level 门 ----
assert wants_item("item") and wants_item("both") and wants_item("crowd") and wants_item("all")
assert not wants_item("campaign")
assert wants_crowd("crowd") and wants_crowd("all")
assert not wants_crowd("campaign") and not wants_crowd("item") and not wants_crowd("both")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python test_alimama_map.py`
Expected: FAIL — `ImportError: cannot import name 'map_crowd_row'`

- [ ] **Step 3: 实现** — 在 `collect_alimama_promo.py` 里：

3a. 常量区（`ADGROUP_URL` 下面）加：

```python
CROWD_URL = "https://one.alimama.com/crowd/horizontal/findPage.json"
```

3b. 在 `is_standard` 附近加 level 门：

```python
def wants_item(level):
    """item 层是人群层的前提（人群行要 join 单元拿 item_id），凡采人群都包含 item。"""
    return level in ("item", "both", "crowd", "all")


def wants_crowd(level):
    return level in ("crowd", "all")
```

3c. 在 `map_adgroup_row` 之后加 `map_crowd_row`：

```python
def map_crowd_row(crowd_row, adgroup, stat_date, shop_id, plan_type, report_source):
    """一个 (单元,人群) 节点 → 一行 promo_cost_item_daily。

    reportInfoList 里没有 charge 键 = 该人群当天在该单元没有投放数据, 不写 0 行。
    entity_key 必须 "<adgroupId>:<crowdId>" —— crowdId 是每单元实例化的, 单用不唯一。
    item_id 只能从单元层 join 回来: 人群行本身不带 material。
    """
    rl = crowd_row.get("reportInfoList")
    info = rl[0] if isinstance(rl, list) and rl else None
    if not isinstance(info, dict) or "charge" not in info:
        return None, "no_data"
    cid = crowd_row.get("campaignId") or adgroup.get("campaignId")
    if cid is None:
        return None, "no_campaign"
    crowd_id = str(crowd_row.get("crowdId") or "")
    if not crowd_id:
        return None, "no_crowd_id"
    unit_id = str(crowd_row.get("adgroupId") or adgroup.get("adgroupId") or "")
    item_id = item_id_of(adgroup)
    if not item_id:
        return None, "no_item_id"
    crowd = crowd_row.get("crowd") or {}
    title = adgroup.get("adgroupName") or info.get("adgroupName")
    row = {
        "shop_id": shop_id if shop_id is not None else 0,
        "platform_code": PLATFORM_CODE,
        "stat_date": stat_date,
        "plan_type": plan_type,
        "dimension": "crowd",
        "entity_key": f"{unit_id}:{crowd_id}",
        "entity_id": crowd_id,
        "entity_name": crowd.get("crowdName") or info.get("crowdName"),
        "item_id": item_id,
        "item_name": title,
        "campaign_id": str(cid),
        "campaign_name": adgroup.get("campaignName"),
        "unit_id": unit_id,
        "unit_name": title,
        "report_source": report_source,
        "raw_json": json.dumps(crowd_row, ensure_ascii=False),
    }
    for src, col, kind in FIELD_MAP:
        row[col] = cast(info.get(src), kind)
    return row, None
```

3d. 在 `fetch_adgroups` 之后加 `crowd_body` 与 `fetch_crowds`：

```python
def crowd_body(tpl, biz_code, campaign_id, day, offset, page_size):
    """人群层请求体。sourceList 必须放在 rptQuery.conditionList 里; 不给 adgroupIdList
    —— 实测按 campaignIdList 一次就返回该计划全部单元的人群行(276 行 / 69 单元)。"""
    return {
        "offset": offset, "pageSize": page_size, "orderField": "", "orderBy": "",
        "bizCode": biz_code, "mx_bizCode": biz_code,
        "campaignIdList": [str(campaign_id)],
        "rptQuery": {"fields": FIELDS_STR, "conditionList": [{
            "sourceList": ["adgroup_detail", "crowd_list"],
            "startTime": day, "endTime": day, "isRt": False}]},
        "csrfId": tpl["body"].get("csrfId"),
        "loginPointId": tpl["body"].get("loginPointId"),
    }


async def fetch_crowds(page, tpl, biz_code, campaign_id, day, offset, page_size):
    body = crowd_body(tpl, biz_code, campaign_id, day, offset, page_size)
    url = CROWD_URL + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=" + biz_code
    r = await page.evaluate("""async ([u, h, b]) => {
        const res = await fetch(u, {method:'POST', headers:h, body:JSON.stringify(b), credentials:'include'});
        return {status: res.status, text: await res.text()};
    }""", [url, tpl["headers"], body])
    return r["status"], r["text"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python test_alimama_map.py`
Expected: PASS — 末行 `OK: collect_alimama_promo 纯函数全部断言通过`

---

### Task 2: 采集器接线（人群层下钻 + 单元级放开 #2/#4 + argparse）

**Files:**
- Modify: `automation/tb-auto/collect_alimama_promo.py`

**Interfaces:**
- Consumes: Task 1 的 `map_crowd_row` / `fetch_crowds` / `wants_item` / `wants_crowd` / `CROWD_URL`
- Produces:
  - `collect_items(...) -> (rows, seen, pages, adgroups)`（由三元组改为四元组）
  - `collect_crowds(page, tpl, biz_code, campaign_id, day, adgroup_by_id, plan_type, args) -> (rows, seen, pages)`
  - 新 CLI 参数：`--crowd-campaign-ids`（默认 `83392643008`）、`--include-campaign-ids`（默认 `83949710619,83340870410`）、`--crowd-page-size`（默认 500）、`--level` 增 `crowd|all`

- [ ] **Step 1: `collect_items` 返回 adgroup 原始列表** — 在函数开头 `rows, seen, offset, pages = [], 0, 0, 0` 后加 `adgroups = []`；在 `for a in lst:` 循环体第一行加 `adgroups.append(a)`；把末尾 `return rows, seen, pages` 改为 `return rows, seen, pages, adgroups`，并更新 docstring 一句：

```python
    """按计划翻完所有单元(=宝贝)。返回 (可入库的行, 扫到的单元总数, 翻了几页, adgroup 原始列表)。

    第四项给人群层 join item_id 用：人群行不带 material，只能靠 adgroupId 从单元对象里取。
    """
```

- [ ] **Step 2: 加 `collect_crowds`** — 在 `collect_items` 之后加：

```python
async def collect_crowds(page, tpl, biz_code, campaign_id, day, adgroup_by_id, plan_type, args):
    """按计划采一次人群层(不给 adgroupIdList → 一次回全计划行)。返回 (行, 扫到行数, 页数)。

    adgroup_by_id 里没有的单元跳过：拿不到 material → 没有 item_id，落了也 join 不上商品。
    """
    rows, seen, offset, pages = [], 0, 0, 0
    while pages < MAX_PAGES:
        status, text = await fetch_crowds(page, tpl, biz_code, campaign_id, day,
                                          offset, args.crowd_page_size)
        if hit_risk(text):
            log(f"!! 人群层 {day} 计划{campaign_id} 命中风控")
            break
        try:
            j = json.loads(text)
        except Exception:
            log(f"  人群层非 JSON 响应 HTTP {status} offset={offset}")
            break
        data = j.get("data") or {}
        lst = data.get("list") or []
        seen += len(lst)
        for cr in lst:
            adg = adgroup_by_id.get(str(cr.get("adgroupId") or ""))
            if adg is None:
                continue
            row, _reason = map_crowd_row(cr, adg, day, args.shop_id, plan_type,
                                         f"alimama-crowd:{biz_code}")
            if row is not None:
                rows.append(row)
        with open(os.path.join(RAW_DIR, f"crowds_{campaign_id}_{day}_{offset}.json"), "w",
                  encoding="utf-8") as f:
            f.write(text)
        pages += 1
        count = data.get("count") or seen
        if offset + args.crowd_page_size >= int(count) or not lst:
            break
        offset += args.crowd_page_size
        await asyncio.sleep(args.gap)
    return rows, seen, pages
```

- [ ] **Step 3: `run()` 起始处解析白名单** — 在 `log(f"待采 ...")` 之前加：

```python
    crowd_cids = {s.strip() for s in (args.crowd_campaign_ids or "").split(",") if s.strip()}
    include_cids = {s.strip() for s in (args.include_campaign_ids or "").split(",") if s.strip()}
    log(f"人群层白名单 {sorted(crowd_cids)}；单元级强制包含 {sorted(include_cids)}")
```

- [ ] **Step 4: 计划层保留判据放开** — 把：

```python
                        if not is_standard(c.get("bidType"), not args.all_bid_types):
                            skipped_bidtype += 1
                            continue
```

改为：

```python
                        keep = (is_standard(c.get("bidType"), not args.all_bid_types)
                                or str(c.get("campaignId")) in include_cids)
                        if not keep:
                            skipped_bidtype += 1
                            continue
```

- [ ] **Step 5: 单元层门 + 调用改四元组 + 人群层下钻** — 把这段：

```python
                    # 宝贝粒度：只对"当天确实花了钱"的标准计划下钻，其余计划没有可归因的东西
                    if args.level not in ("item", "both"):
                        continue
                    plan_charge = {r["campaign_id"]: r["charge"] for r in rows}
                    for cid in plan_charge:
                        item_rows, cnt, pages = await collect_items(
                            page, tpl, biz_code, cid, day, args, plan_type)
```

改为：

```python
                    # 宝贝粒度：只对"当天确实花了钱"的计划下钻，其余计划没有可归因的东西
                    if not wants_item(args.level):
                        continue
                    plan_charge = {r["campaign_id"]: r["charge"] for r in rows}
                    for cid in plan_charge:
                        item_rows, cnt, pages, adgroups = await collect_items(
                            page, tpl, biz_code, cid, day, args, plan_type)
```

并把该 for 循环体末尾（`await asyncio.sleep(args.gap)` 那一行之前）插入人群层：

```python
                        # 人群层：只对白名单计划（默认 #1 关键词标准），且要采人群的 level
                        if wants_crowd(args.level) and str(cid) in crowd_cids:
                            by_id = {str(a.get("adgroupId")): a for a in adgroups
                                     if a.get("adgroupId") is not None}
                            crowd_rows, cseen, cpages = await collect_crowds(
                                page, tpl, biz_code, cid, day, by_id, plan_type, args)
                            for r in crowd_rows:
                                r["import_batch"] = batch_tag
                            if crowd_rows:
                                if args.dry_run:
                                    item_ok += len(crowd_rows)
                                else:
                                    item_ok += upsert(conn, "promo_cost_item_daily", ITEM_COLS,
                                                      crowd_rows, batch_tag)
                            item_total += cseen
                            log(f"    人群 {cid}: 有数{len(crowd_rows)}/{cseen} 页{cpages}")
                            await asyncio.sleep(args.gap)
```

- [ ] **Step 6: argparse 扩参** — 把 `--level` 那行替换为下列四行，并新增三个参数（放在 `--level` 之后）：

```python
    ap.add_argument("--level", choices=("campaign", "item", "crowd", "both", "all"),
                    default="campaign",
                    help="campaign=只采计划日报 item/both=计划+宝贝 crowd/all=计划+宝贝+人群")
    ap.add_argument("--crowd-campaign-ids", default="83392643008",
                    help="只对这些计划采人群层(逗号分隔); 默认 #1 关键词标准计划")
    ap.add_argument("--include-campaign-ids", default="83949710619,83340870410",
                    help="这些计划不论 bidType 都收单元行(逗号分隔); 默认 #2 关键词智能 / #4 人群控投产")
    ap.add_argument("--crowd-page-size", type=int, default=500, help="人群层分页大小")
```

- [ ] **Step 7: 语法自检 + 纯函数回归**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python -m py_compile collect_alimama_promo.py && ../venv/bin/python test_alimama_map.py`
Expected: 两行都无输出/无异常，末行 `OK: ...`

- [ ] **Step 8: 实地 dry-run 验证（只读，需 9222 已登录万相台）**

Run（把日期换成昨天）:
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python collect_alimama_promo.py \
  --from 2026-10-11 --to 2026-10-11 --level all --dry-run \
  --crowd-campaign-ids 83392643008 --include-campaign-ids 83949710619,83340870410 --gap 2
```
Expected: 日志出现 `人群层白名单 ['83392643008']`；`关键词关键字 2026-10-11: 计划N 写入M ...`；至少一行 `    人群 83392643008: 有数K/276 页1`（`K` 可能很小，10-11 实测带 charge 的仅 5 行）；`宝贝 83949710619` 与 `宝贝 83340870410` 也有 `Σ花费` 行（证明 #2/#4 单元级已放开）。**dry-run 不写库、不进台账。**

---

### Task 3: 每日 22:00 作业切到人群层

**Files:**
- Modify: `automation/tb-auto/cron_alimama_promo.sh:44-45`

**Interfaces:**
- Consumes: Task 2 的 CLI 参数

- [ ] **Step 1: 改采集命令** — 把：

```bash
echo "[$(date '+%F %T')] 开始采集（滚动 ${DAYS} 天，计划+宝贝两层）" >> "$LOG"
$PY collect_alimama_promo.py --level both --days "$DAYS" --gap 4 >> "$LOG" 2>&1
```

改为：

```bash
echo "[$(date '+%F %T')] 开始采集（滚动 ${DAYS} 天，计划+宝贝+人群三层）" >> "$LOG"
$PY collect_alimama_promo.py --level all --days "$DAYS" --gap 4 \
  --crowd-campaign-ids 83392643008 \
  --include-campaign-ids 83949710619,83340870410 >> "$LOG" 2>&1
```

- [ ] **Step 2: 语法自检**

Run: `bash -n /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/cron_alimama_promo.sh`
Expected: 无输出（语法 OK）

- [ ] **Step 3: 三处调度对齐不变，确认无漂移** — 该作业仍是同一脚本、同一时刻，`ingest_dataset.cron_expr` 与 task-progress 卡片无需改。跑：

Run: `cd /Users/qyk9527/ideaProject/spzx-parent && python3 scripts/check-consistency.py`
Expected: 退出码 0（详见 Task 9 的判读）。

---

### Task 4: 子集校验脚本（Σ人群 click ≤ 单元 click）

**Files:**
- Create: `automation/tb-auto/check_crowd_subset.py`

**Interfaces:**
- Consumes: `promo_cost_item_daily` 里 `dimension='crowd'` 与 `dimension='item'` 的行
- Produces: 退出码 0=无违反，1=有违反；打印违反明细

- [ ] **Step 1: 写脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子集校验: 对每个 (item_id, campaign_id, stat_date), Σ人群 click 应 <= 单元 click。

超了说明平台把一次点击记到了多个人群实例(重复计数), 页面占比会 >100%, 必须人工看。
一次性/周期性自查脚本, 不写库。跑法:
  automation/venv/bin/python check_crowd_subset.py --from 2026-10-01 --to 2026-10-11
"""
import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cron_batch import DB_CONFIG  # noqa: E402
import pymysql  # noqa: E402

SQL = """
SELECT c.item_id, c.campaign_id, c.stat_date, c.crowd_click, i.item_click
FROM (SELECT item_id, campaign_id, stat_date, SUM(click) AS crowd_click
      FROM promo_cost_item_daily
      WHERE dimension = 'crowd' AND stat_date BETWEEN %s AND %s
      GROUP BY item_id, campaign_id, stat_date) c
JOIN (SELECT item_id, campaign_id, stat_date, SUM(click) AS item_click
      FROM promo_cost_item_daily
      WHERE dimension = 'item' AND stat_date BETWEEN %s AND %s
      GROUP BY item_id, campaign_id, stat_date) i
  ON i.item_id = c.item_id AND i.campaign_id = c.campaign_id AND i.stat_date = c.stat_date
WHERE c.crowd_click > i.item_click
ORDER BY (c.crowd_click - i.item_click) DESC
LIMIT %s
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom",
                    default=(date.today() - timedelta(days=14)).isoformat())
    ap.add_argument("--to", dest="dto", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(SQL, (a.dfrom, a.dto, a.dfrom, a.dto, a.limit))
            bad = cur.fetchall()
    finally:
        conn.close()

    if not bad:
        print(f"OK: {a.dfrom}~{a.dto} 无「人群 click > 单元 click」的 (item,campaign,date)")
        return 0
    print(f"!! {len(bad)} 处人群点击超过单元点击（疑似重复计数）:")
    for item_id, cid, day, cc, ic in bad:
        print(f"  {day} 计划{cid} 宝贝{item_id}: 人群{cc} > 单元{ic}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 语法自检**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python -m py_compile check_crowd_subset.py`
Expected: 无输出

- [ ] **Step 3: 空库期实跑（此刻表里还没有 crowd 行，应直接 OK）**

Run: `../venv/bin/python check_crowd_subset.py`
Expected: `OK: ... 无「人群 click > 单元 click」...`，退出码 0

---

### Task 5: `PromoItemVo` 加两列（spzx-model）

**Files:**
- Modify: `spzx-model/src/main/java/com/joker/spzx/model/vo/promo/PromoItemVo.java`

**Interfaces:**
- Produces: `PromoItemVo.getCrowdClick(): Long`、`getCrowdClickShare(): BigDecimal`（Lombok `@Data`）

- [ ] **Step 1: 加字段** — 在 `click` 字段之后加：

```java
    @Schema(description = "该宝贝各人群点击之和（只有关键词标准计划的单元采了人群层）；null=没有人群数据")
    private Long crowdClick;

    @Schema(description = "推广人群占比 = 人群点击 / 总点击 × 100（百分数，如 30.00）；click=0 或无人群数据为 null")
    private BigDecimal crowdClickShare;
```

- [ ] **Step 2: 装 jar 到 ~/.m2**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && cd /Users/qyk9527/ideaProject/spzx-parent && mvn install -pl spzx-model -DskipTests -q`
Expected: 退出码 0（无输出或只有下载日志）

---

### Task 6: `applyCrowdShare` 纯函数 + 接入 items()（TDD）

**Files:**
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/service/promo/PromoReportService.java`
- Test: `spzx-manager/src/test/java/com/joker/spzx/manager/service/promo/PromoReportServiceTest.java`

**Interfaces:**
- Consumes: Task 5 的 `getCrowdClick()`/`setCrowdClickShare()`
- Produces: `PromoReportService.applyCrowdShare(PromoItemVo)`（static void）

- [ ] **Step 1: 写失败测试** — 在 `PromoReportServiceTest` 末尾（最后一个 `}` 之前）加：

```java
    @Test
    void 人群占比先加总再除且分母为0出null() {
        PromoItemVo v = new PromoItemVo();
        v.setClick(10L);
        v.setCrowdClick(3L);
        PromoReportService.applyCrowdShare(v);
        assertEquals(0, new java.math.BigDecimal("30.00").compareTo(v.getCrowdClickShare()));

        PromoItemVo none = new PromoItemVo();
        none.setClick(10L);
        none.setCrowdClick(null);          // 没采到人群 → null，不是 0
        PromoReportService.applyCrowdShare(none);
        assertNull(none.getCrowdClickShare());

        PromoItemVo zeroDiv = new PromoItemVo();
        zeroDiv.setClick(0L);              // 分母为 0 → null，不是除零异常也不是 0
        zeroDiv.setCrowdClick(0L);
        PromoReportService.applyCrowdShare(zeroDiv);
        assertNull(zeroDiv.getCrowdClickShare());

        PromoItemVo odd = new PromoItemVo();
        odd.setClick(3L);
        odd.setCrowdClick(1L);
        PromoReportService.applyCrowdShare(odd);
        assertEquals(0, new java.math.BigDecimal("33.33").compareTo(odd.getCrowdClickShare()));

        PromoItemVo zeroShare = new PromoItemVo();
        zeroShare.setClick(5L);
        zeroShare.setCrowdClick(0L);       // 有人群行但点击为 0 → 0.00（是算出来的零）
        PromoReportService.applyCrowdShare(zeroShare);
        assertEquals(0, java.math.BigDecimal.ZERO.compareTo(zeroShare.getCrowdClickShare()));
    }
```

- [ ] **Step 2: 跑测试确认失败**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && cd /Users/qyk9527/ideaProject/spzx-parent && mvn test -pl spzx-manager -am -Dtest=PromoReportServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: 编译失败/报 `applyCrowdShare` 不存在 → BUILD FAILURE

- [ ] **Step 3: 实现** — 在 `PromoReportService` 里，`applyProfit` 之后加：

```java
    /**
     * 纯函数：推广人群占比 = 人群点击 / 总点击 × 100（百分数）。
     *
     * 分子已在 SQL 里按 item_id 汇总好，这里只做除法 —— 与「比率一律用汇总后的分子分母重算」
     * 同一条纪律。总点击为 0 或没采到人群（crowdClick=null）都出 null，不粉饰成 0。
     */
    public static void applyCrowdShare(PromoItemVo vo) {
        Long cc = vo.getCrowdClick();
        Long click = vo.getClick();
        if (cc == null || click == null || click == 0) {
            vo.setCrowdClickShare(null);
            return;
        }
        vo.setCrowdClickShare(BigDecimal.valueOf(cc)
                .multiply(HUNDRED)
                .divide(BigDecimal.valueOf(click), 2, RoundingMode.HALF_UP));
    }
```

并把 `items()` 里的：

```java
        res.getRecords().forEach(PromoReportService::applyProfit);
```

改为：

```java
        res.getRecords().forEach(PromoReportService::applyProfit);
        res.getRecords().forEach(PromoReportService::applyCrowdShare);
```

- [ ] **Step 4: 跑测试确认通过**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && cd /Users/qyk9527/ideaProject/spzx-parent && mvn test -pl spzx-manager -am -Dtest=PromoReportServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Tests run: 8, Failures: 0（原 7 条 + 新 1 条）

---

### Task 7: `selectItems` 增人群聚合 LEFT JOIN

**Files:**
- Modify: `spzx-manager/src/main/resources/mapper/PromoReportMapper.xml:98-189`

**Interfaces:**
- Consumes: `promo_cost_item_daily` 的 `dimension='crowd'` 行；参数 `dateFrom/dateTo/planType/campaignId`（均已在 mapper 接口上）
- Produces: `selectItems` 结果多出 `crowdClick` 列

- [ ] **Step 1: 加 LEFT JOIN 到人群聚合** — 在内层子查询的 `LEFT JOIN (SELECT platform_type, ...) fee ON ...` 之后、`<where>` 之前插入：

```xml
                     <!-- 人群点击：只有 #1 关键词标准计划的单元有人群行(dimension='crowd')。
                          按 item_id 先聚成一行再 join，避免多个人群把 item 行数放大。
                          过滤口径与 item 行一致(date/plan_type/campaignId)，keyword 不参与——
                          keyword 只决定哪些宝贝显示，不改变某个宝贝内部的人群构成。 -->
                     LEFT JOIN (SELECT c.item_id                                                    AS item_id,
                                       SUM(c.click)                                                  AS crowd_click
                                FROM promo_cost_item_daily c
                                WHERE c.dimension = 'crowd'
                                  AND c.stat_date BETWEEN #{dateFrom} AND #{dateTo}
                                  <if test="planType != null and planType != '' and planType != 'all'">
                                      AND c.plan_type = #{planType}
                                  </if>
                                  <if test="campaignId != null and campaignId != ''">
                                      AND c.campaign_id = #{campaignId}
                                  </if>
                                GROUP BY c.item_id) cc ON cc.item_id = i.item_id
```

- [ ] **Step 2: 选出该列** — 在内层 SELECT 的最后一行 `MAX(fee.payment_fee_rate) AS paymentFeeRate` 后面加逗号并追加：

```xml
                   ,
                   MAX(cc.crowd_click)                                                AS crowdClick
```

（注意：`MAX(fee.payment_fee_rate) AS paymentFeeRate` 原本是内层 SELECT 的最后一项，**不要漏掉新增的逗号**。`MAX` 是满足 ONLY_FULL_GROUP_BY 的写法，`cc` 每个 item_id 只有一行。）

- [ ] **Step 3: 编译**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q`
Expected: 退出码 0

- [ ] **Step 4: 实跑 SQL 核对手工值** — 先重建 cnf：

Run: `cd /Users/qyk9527/ideaProject/spzx-parent && python3 scripts/mysql-cnf.py --test`
然后（此刻可能还没有 crowd 行；若 Task 2 的落库跑过、或 22:00 作业已跑，则有值）：
```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf -N -e "
SELECT c.item_id, SUM(c.click) crowd_click
FROM db_spzx.promo_cost_item_daily c
WHERE c.dimension='crowd' GROUP BY c.item_id ORDER BY crowd_click DESC LIMIT 5;"
```
Expected: 有行则值与页面/接口的 `crowdClick` 一致；无行则 `crowdClick` 全为 null（前端显示「—」）。若此时尚无数据，本步改为在 Task 9 的端到端验证里复核。

---

### Task 8: 前端宝贝页加两列

**Files:**
- Modify: `/Users/qyk9527/webstormProject/spzx-admin/src/views/mall/promoReport.vue`（`columns` 数组，约 542 行 `click` 列之后）

**Interfaces:**
- Consumes: `crowdClick`（Long）、`crowdClickShare`（百分数 BigDecimal）
- Produces: 无（UI）

- [ ] **Step 1: 加两列** — 在 `{ prop: 'click', label: '点击', width: 80 },` 之后插入：

```js
  {
    prop: 'crowdClick',
    label: '人群点击',
    width: 90,
    formatter: r => intOf(r.crowdClick),
  },
  {
    prop: 'crowdClickShare',
    label: '人群占比',
    width: 100,
    formatter: r => pct(r.crowdClickShare),
  },
```

- [ ] **Step 2: 构建自检**

Run: `cd /Users/qyk9527/webstormProject/spzx-admin && npm run build`
Expected: 构建成功（无 lint/类型错误），产物生成

- [ ] **Step 3: 页面肉眼核对（需 8501 与前端 dev/静态产物在线）** — 打开「运营 > 推广日报」，宝贝表看到「人群点击 / 人群占比」两列；只有 #1（`83392643008`）的行有值，其余为「—」；占比列带 `%`。

---

### Task 9: 一致性门 + 端到端复核 + 留痕

**Files:**
- 无代码改动（验证 + 台账）

- [ ] **Step 1: 跑一致性门**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent && python3 scripts/check-consistency.py; echo "rc=$?"`
Expected: 退出码 0。若有 fail，先 `--selftest` 证明它报得出红，再逐条比对是否本次改动引入（本次不动 cron 时刻/端点/判据副本，理论上 0 fail）。

- [ ] **Step 2: 全量单测（除 EmailTest）**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && cd /Users/qyk9527/ideaProject/spzx-parent && mvn test -pl spzx-manager -am -Dtest='!EmailTest' -Dsurefire.failIfNoSpecifiedTests=false`
Expected: BUILD SUCCESS，无非 EmailTest 的红。

- [ ] **Step 3: 端到端（真落库 → 接口 → 页面）** — 确认 9222 窗口模式已登录万相台、8501 在跑，跑一次**真实**采集（小窗口，例如近 2 天）：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto && ../venv/bin/python collect_alimama_promo.py \
  --from 2026-10-10 --to 2026-10-11 --level all --gap 2 \
  --crowd-campaign-ids 83392643008 --include-campaign-ids 83949710619,83340870410
```
然后：
```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf -N -e "
SELECT COUNT(*), COUNT(DISTINCT item_id) FROM db_spzx.promo_cost_item_daily
WHERE dimension='crowd';"
../venv/bin/python check_crowd_subset.py --from 2026-10-10 --to 2026-10-11
```
Expected: crowd 行数 > 0；子集校验 OK；`curl 'http://localhost:8501/admin/promo/report/items/1/20'`（带登录态或直接看页面）里 #1 的宝贝 `crowdClick`/`crowdClickShare` 有值且占比 ≤ 100。

- [ ] **Step 4: 留痕**

Run:
```bash
cd /Users/qyk9527/ideaProject/spzx-parent && python3 scripts/log_work.py \
  --module "推广日报" --title "单元×人群采集 + 人群点击占比" \
  --status done --note "collect_alimama_promo.py 加人群层(计划级单查)、宝贝页加两列；check_crowd_subset.py 兜重复计数"
```
Expected: 命令回显写入成功（`create_by=-1` 哨兵行）。

---

## Self-Review

**1. Spec coverage:**

| Spec 段落 | 落地任务 |
|---|---|
| §2.2 人群接口（含 2026-10-12 计划级修正） | Task 1（`crowd_body`/`fetch_crowds`）、Task 2（`collect_crowds`） |
| §3 数据模型（复用表、字段取值、自然键） | Task 1（`map_crowd_row`）+ Task 2（`upsert` 走 `ITEM_COLS`） |
| §4.1 `--level` 扩值 | Task 1（`wants_item`/`wants_crowd`）、Task 2 Step 6 |
| §4.2 人群层逐计划 + `map_crowd_row` + join item_id | Task 1、Task 2 Step 1/2/5 |
| §4.3 `--crowd-campaign-ids` | Task 2 Step 6 |
| §4.4 `--include-campaign-ids` 放开 #2/#4 | Task 2 Step 4/6 |
| §4.5 人群行与单元行同表同批（台账） | Task 2 Step 5（`item_total/item_ok` 归并） |
| §5 后端 `crowdClick`/`crowdClickShare` | Task 5、Task 6、Task 7 |
| §6 前端两列 | Task 8 |
| §7 调度改 cron | Task 3 |
| §8.1 子集校验 | Task 4 |
| §8.4 单测 | Task 1、Task 6 |
| §8.5/§9 一致性门 | Task 3 Step 3、Task 9 Step 1 |

无遗漏。

**2. Placeholder scan:** 无 TBD/TODO；每个代码步都给了可直接粘贴的代码。Task 7 Step 4 与 Task 9 Step 3 是「当前可能还没数据」的实跑式验证，已给出无数据时的处置（改为 Task 9 复核），不是占位。

**3. Type consistency:**
- `map_crowd_row` 六参签名在 Task 1 定义、Task 2 调用一致（`crowd_row, adgroup, stat_date, shop_id, plan_type, report_source`）。
- `collect_items` 由 `(rows, seen, pages)` 改四元组，Task 2 Step 1 定义、Step 5 解包一致。
- `collect_crowds` 七参在 Step 2 定义、Step 5 调用一致（`... day, ad_by_id, plan_type, args`）。
- Java：`getCrowdClick`/`setCrowdClickShare`（Task 5 Lombok）与 Task 6 使用一致；mapper `crowdClick` 别名与 VO 字段名一致。
