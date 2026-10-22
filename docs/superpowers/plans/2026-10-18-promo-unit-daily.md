# 万相台标准计划「单元日报」实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对万相台标准计划 84290744044 打通单元级关键词日报采集（词层接口探针 → 采集器词层 → 落库），并在运营后台新增「推广·单元日报」页面（单元列表 + 逐日趋势 + 关键词明细 + 人群点击占比）。

**Architecture:** 采集侧在 `collect_alimama_promo.py` 现有四层（计划/单元/人群）上加第五层「词」，词行与人群行同构落 `promo_cost_item_daily`（dimension='keyword'，entity_key 复合 `<adgroupId>:<词文本>`），台账并入现有 `promo_cost_detail` 批次、不新增 dataset。后端新增只读 `PromoUnitController`（4 端点查同一张明细表按 unit 聚合），前端新页面 `promoUnit.vue` 不动现有推广日报页。

**Tech Stack:** Python 3.9（Playwright async + CDP 9222 + pymysql）、Spring Boot 3.3.5 / MyBatis-Plus（spzx-manager + spzx-model）、Vue 3 + Element Plus + echarts（spzx-admin）。

**Spec:** `docs/superpowers/specs/2026-10-18-promo-unit-daily-design.md`（本文所有口径以它为准；Task 1 完成后要把探针结论回填它的 §2）。

## Global Constraints

- **绝不 `git commit` / `git add`**：spzx-parent 与 spzx-admin 两个仓库都由用户自己决定提交。本计划所有任务**没有 commit 步骤**——改完文件、跑完验证即收工。
- 后端编译（本机无 mvn，用 IDEA 内置；先 install model——VO 在 spzx-model 里）：
  ```bash
  export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
  mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am
  ```
- 后端单测**禁止裸 `mvn test`**（会带上要连库的 EmailTest），必须：
  ```bash
  mvn test -pl spzx-manager -am -Dtest='PromoUnitServiceTest' -Dsurefire.failIfNoSpecifiedTests=false
  ```
- Python 统一 `automation/venv/bin/python`；采集器纯函数单测跑法（cwd 必须是 tb-auto，`import collect_alimama_promo` 靠 cwd）：
  ```bash
  # workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
  ../venv/bin/python test_alimama_map.py
  ```
- MySQL 命令行一律 `mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "..."`（口令不进命令行）；`/tmp/spzx_my.cnf` 被清了先 `python3 scripts/mysql-cnf.py` 重建。
- **9222 Chrome 时段红线**：探针（Task 1）和 30 天回补（Task 3）都要在 9222 上开页面，必须避开：白天建档补跑窗口（工作日 ~21:40 前在跑）、19:30 ISV 同步轮、22:00 推广采集。执行前先 `pgrep -f "sycm_item_snapshot|assign_shop_category|collect_1688_full|auto_list|backfill_offer_archive" ` 确认没有别的任务在 9222 上跑。
- 采集器 `--crowd-campaign-ids` 的**默认值不动**（仍 `83392643008`）；扩入 84290744044 只发生在 `cron_alimama_promo.sh` 命令行上（命令行是唯一真相）。
- 词行 `entity_key` 一律复合 `<adgroupId>:<词文本>`（同词多单元不互踩）。
- 占比纪律：**先加总再除**（SQL 只出分子分母，service 除）、分母 0 出 NULL 不出 0、`ROUND_HALF_UP` 2 位。
- 不动现有推广日报页（`promoReport.vue`）与 `/admin/promo/report/*` 接口。

---

### Task 1: 词级报表探针（gate 任务，有分支）

**Files:**
- Create: `automation/tb-auto/probe_alimama_word_tab.py`
- Create（运行产物，gitignored 目录）: `automation/tb-auto/probe_alimama_out/`（index.json / resp_NNN.json / word_template.json）
- Modify: `docs/superpowers/specs/2026-10-18-promo-unit-daily-design.md`（§2 回填实施记录）

**Interfaces:**
- Produces: `probe_alimama_out/word_template.json` —— Task 2 的依据，须人工确认四个事实：①词级报表接口 URL；②`sourceList` 第二项（预期 `word_list`）；③词 id 字段名（预期 `bidwordId`）；④词文本字段名（预期 `word`）；⑤指标在 `reportInfoList[0]`（预期同 crowd）。
- 复用: `collect_alimama_promo.py` 的 `borrow_template` / `fetch_adgroups`（import 复用，不改它们）。

**背景（失败史，不要重走）**：`report/query.json`+`tab=word` 只回计划汇总；旧 `probe_alimama_item_tab.py` 只抓到 `component/findList.json`。这次**记录全部 .json 响应体**，先抓全再筛。

- [ ] **Step 1: 写探针脚本（全文如下）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_word_tab.py — 抓万相台单元详情页【关键词】tab 的词级报表 XHR.

背景: collect_alimama_promo.py 计划/单元/人群三层已通, 词层接口形态未知。
前两轮探针(report/query.json+tab=word、监听 search-detail 页)只拿到计划汇总行与
component/findList.json —— 这次记录**全部** .json 响应体, 先抓全再人工筛。

用法(先确保 9222 Chrome 已登录万相台、窗口模式、无其他长任务在 9222 上跑):
    automation/venv/bin/python tb-auto/probe_alimama_word_tab.py \
        --campaign-id 84290744044 [--adgroup-id <id>] [--seconds 40]

产物: tb-auto/probe_alimama_out/ 下
  index.json          每个响应一行(file/url/status/长度/命中特征)
  resp_NNN.json       完整响应体
  word_template.json  命中词行特征的候选清单(人工确认后作为采集器词层依据)
只读: 只打开页面与监听, 不点任何写操作按钮。
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import collect_alimama_promo as cap  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
DETAIL_URL = ("https://one.alimama.com/index.html#!/manage/search-detail"
              "?mx_bizCode=onebpSearch&bizCode=onebpSearch&startTime={d}&endTime={d}"
              "&campaignId={cid}&tab=&adgroupId={aid}")


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


async def main(a):
    os.makedirs(OUT, exist_ok=True)
    day = time.strftime("%F")
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    seen = []
    idx = {"n": 0}

    def on_resp(resp):
        if ".json" not in resp.url:
            return
        n = idx["n"] = idx["n"] + 1
        name = f"resp_{n:03d}.json"

        async def grab():
            try:
                body = await resp.text()
            except Exception:
                body = ""
            hits = [w for w in ("bidword", "reportInfoList", "crowdId", "wordList") if w in body]
            seen.append({"file": name, "url": resp.url[:300], "status": resp.status,
                         "len": len(body), "hits": hits})
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
                f.write(body)

        asyncio.ensure_future(grab())

    page = await ctx.new_page()
    page.on("response", on_resp)
    try:
        tpl = await cap.borrow_template(page, "onebpSearch", day)
        if not tpl:
            log("!! 没借到 findPage 参数(登录态掉了?) —— 人工打开万相台后台后再跑")
            return 2
        aid = a.adgroup_id
        if not aid:
            status, text = await cap.fetch_adgroups(page, tpl, "onebpSearch",
                                                    a.campaign_id, day, 0, 200)
            lst = ((json.loads(text).get("data") or {}).get("list")) or []
            if not lst:
                log("!! 该计划拿不到单元, 用 --adgroup-id 手动指定")
                return 2
            aid = lst[0].get("adgroupId")
        log(f"单元详情页 adgroupId={aid}, 监听 {a.seconds}s …")
        await page.goto(DETAIL_URL.format(d=day, cid=a.campaign_id, aid=aid),
                        wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(a.seconds)
        try:
            await page.click('text=人群', timeout=5000)
            await asyncio.sleep(8)
            log("已切【人群】tab(用于核对 crowd 接口形态)")
        except Exception:
            log("未找到人群 tab(该单元可能没配人群), 继续")
    finally:
        with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=1)
        try:
            await page.close()
        except Exception:
            pass
        await b.close()

    cand = [s for s in seen if "bidword" in s["hits"] and "reportInfoList" in s["hits"]]
    crowd = [s for s in seen if "crowdId" in s["hits"]]
    with open(os.path.join(OUT, "word_template.json"), "w", encoding="utf-8") as f:
        json.dump({"candidates": cand, "crowd_seen": crowd,
                   "note": "人工确认 URL/sourceList/词id字段/词文本字段 后回填采集器"},
                  f, ensure_ascii=False, indent=1)
    log(f"共记录 {len(seen)} 个 json 响应 → {OUT}")
    for s in cand:
        log(f"  词级候选: {s['file']} len={s['len']} {s['url'][:120]}")
    if not cand:
        log("!! 没有命中 bidword+reportInfoList 的响应 —— 检查 index.json 里点【关键词】tab 后的新增响应")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", default="84290744044")
    ap.add_argument("--adgroup-id", default=None)
    ap.add_argument("--seconds", type=int, default=40)
    sys.exit(asyncio.run(main(ap.parse_args())))
```

- [ ] **Step 2: 语法冒烟**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python -c "import ast; ast.parse(open('probe_alimama_word_tab.py').read())"
```
Expected: 无输出（语法 OK）。

- [ ] **Step 3: 跑探针（执行时机见 Global Constraints 的 9222 红线；跑之前和用户确认时间窗）**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python probe_alimama_word_tab.py --campaign-id 84290744044 --seconds 40
```
Expected: 退出码 0，打印「词级候选」至少一行。若退出码 1（没命中）：看 `index.json` 里 goto 之后的响应、以及手动在页面上点【关键词】tab 后新增的响应，人工找含 `bidword` 的 URL；仍找不到 → **停下找用户**，按 spec §9.1 谈退路（DOM 兜底 / 降级只上单元+人群两层），不要自己改走 DOM 路。

- [ ] **Step 4: 人工确认模板**

打开 `probe_alimama_out/word_template.json` 里 candidates 指向的 `resp_NNN.json`，确认四件事并记录：①完整 URL（路径部分）；②请求 sourceList（从 `index.json` 找不到 body 就看同 URL 的 request——可在探针里临时加 `page.on("request")` 重跑）；③词 id 字段名；④词文本字段名；⑤`reportInfoList[0]` 里是否 charge/click 等字段名与 `FIELD_MAP` 一致。

- [ ] **Step 5: 回填 spec**

把上面四个事实写进 `docs/superpowers/specs/2026-10-18-promo-unit-daily-design.md` §2 末尾，新增小节「**2.1 实施记录（YYYY-MM-DD 探针实测）**」，贴 URL、sourceList、字段名与一行响应样例。Expected: spec §2 不再是「预期形态」而是实测形态。

---

### Task 2: 采集器词层（纯函数 TDD → 接线 → cron）

**Files:**
- Modify: `automation/tb-auto/collect_alimama_promo.py`（常量、5 个新函数、run() 接线、main() 参数）
- Modify: `automation/tb-auto/test_alimama_map.py`（追加词层断言）
- Modify: `automation/tb-auto/cron_alimama_promo.sh:44-47`（命令行加参数）

**Interfaces:**
- Consumes: Task 1 的实测事实（WORD_URL / sourceList / 词字段名；下面代码按「与 crowd 同构」的预期形态写，**Task 1 若发现不同，改 WORD_URL、`word_body` 的 sourceList、`word_of` 的字段名三处，单测 fixture 同步改**）。
- Produces: `map_word_row(word_row, adgroup, stat_date, shop_id, plan_type, report_source) -> (row|None, reason)`、`word_body(tpl, biz_code, campaign_id, day, offset, page_size) -> dict`、`fetch_words(page, tpl, biz_code, campaign_id, day, offset, page_size) -> (status, text)`、`collect_words(page, tpl, biz_code, campaign_id, day, adgroup_by_id, plan_type, args) -> (rows, seen, pages)`、`wants_word(level) -> bool`；命令行 `--word-campaign-ids`（默认 `84290744044`）、`--word-page-size`（默认 500）、`--level` 新增 `word` 值。

- [ ] **Step 1: 追加失败断言（先写测试）**

在 `test_alimama_map.py` 顶部 import 里加 `map_word_row, wants_word, word_body`（import 自 `collect_alimama_promo`），文件末尾 `print` 之前追加：

```python
# ---- 词层: 一个 (单元,词) 节点 → 一行 promo_cost_item_daily ----
# fixture 是按「与 crowd 层同构」的预期形态编的; 探针(Task 1)若发现字段名不同,
# 这里和 word_of/word_body 一起改 —— 两条必须同步, 否则单测绿了采集还是错。
WORD_INFO = {"charge": 5.4, "adPv": 60.0, "click": 7.0, "ctr": 0.1167, "ecpc": 0.7714,
             "alipayInshopAmt": 0.0, "alipayInshopNum": 0.0, "cartInshopNum": 1.0,
             "itemColInshopNum": 1.0, "colNum": 1.0, "bidwordId": 987654321,
             "word": "皮草外套女"}
WORD_ROW = {"adgroupId": 83440680802, "campaignId": 84290744044, "bidwordId": 987654321,
            "word": "皮草外套女", "matchScope": 4, "reportInfoList": [WORD_INFO]}
WADG = {"adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
        "campaignId": 84290744044, "campaignName": "6脉之E标准词提价拉新",
        "material": {"materialId": 1072639258886}}

wrow, wreason = map_word_row(WORD_ROW, WADG, "2026-10-17", 1, "keyword",
                             "alimama-keyword:onebpSearch")
assert wreason is None and wrow is not None
assert wrow["dimension"] == "keyword"
assert wrow["entity_key"] == "83440680802:皮草外套女"   # 复合键: 同词多单元不互踩
assert wrow["entity_id"] == "987654321"
assert wrow["entity_name"] == "皮草外套女"
assert wrow["item_id"] == "1072639258886"               # item_id 来自单元(material)
assert wrow["unit_id"] == "83440680802"
assert wrow["campaign_id"] == "84290744044"
assert wrow["report_source"] == "alimama-keyword:onebpSearch"
assert wrow["charge"] == 5.4 and wrow["click"] == 7 and wrow["cpc"] == 0.7714
# 没有词文本 → 键不完整, 跳过
assert map_word_row({"adgroupId": 1, "campaignId": 2, "reportInfoList": [WORD_INFO]},
                    WADG, "d", 1, "keyword", "s")[1] == "no_word"
# 空 reportInfoList / 无 charge 键 = 当天没投放, 不写 0 行(与 item/crowd 同口径)
assert map_word_row({"adgroupId": 1, "bidwordId": 2, "word": "w", "reportInfoList": None},
                    WADG, "d", 1, "keyword", "s")[1] == "no_data"
assert map_word_row({"adgroupId": 1, "bidwordId": 2, "word": "w",
                     "reportInfoList": [{"roi7d": 0}]},
                    WADG, "d", 1, "keyword", "s")[1] == "no_data"
# 单元拿不到 item_id → 跳过
assert map_word_row(WORD_ROW, {"adgroupName": "x"}, "d", 1, "keyword", "s")[1] == "no_item_id"

# ---- 词请求体: sourceList 必须在 rptQuery.conditionList 里; 按计划一次回全计划词行 ----
wb = word_body({"body": {"csrfId": "C", "loginPointId": "L"}},
               "onebpSearch", 84290744044, "2026-10-17", 0, 500)
assert wb["rptQuery"]["conditionList"][0]["sourceList"] == ["adgroup_detail", "word_list"]
assert wb["campaignIdList"] == ["84290744044"]
assert "adgroupIdList" not in wb
assert wb["csrfId"] == "C" and wb["loginPointId"] == "L"
assert wb["rptQuery"]["conditionList"][0]["isRt"] is False

# ---- level 门: word 含在 all 里; word 依赖 item(要 join 单元拿 item_id) ----
assert wants_word("word") and wants_word("all")
assert not wants_word("campaign") and not wants_word("item")
assert not wants_word("crowd") and not wants_word("both")
assert wants_item("word")
```

- [ ] **Step 2: 跑测试确认红**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python test_alimama_map.py
```
Expected: `ImportError: cannot import name 'map_word_row'`。

- [ ] **Step 3: 实现词层纯函数**

在 `collect_alimama_promo.py`：

(a) 常量区（L42 `CROWD_URL` 之后）加：

```python
# 词层报表接口 —— URL 与 sourceList 以探针产物 probe_alimama_out/word_template.json 为准
# (2026-10-18 实测形态; 若探针发现不同路径, 只改这一行)
WORD_URL = "https://one.alimama.com/bidword/horizontal/findPage.json"
```

(b) `wants_crowd`（L135-136）之后加：

```python
def wants_word(level):
    return level in ("word", "all")
```

(c) `wants_item`（L130-132）改为把 `word` 也算依赖 item（词行要 join 单元拿 item_id）：

```python
def wants_item(level):
    """item 层是人群层/词层的前提（都要 join 单元拿 item_id），凡采人群或词都包含 item。"""
    return level in ("item", "both", "crowd", "all", "word")
```

(d) `crowd_body`（L419-431）之后加 `word_body` 与 `word_of`：

```python
def word_body(tpl, biz_code, campaign_id, day, offset, page_size):
    """词层请求体。sourceList 必须放在 rptQuery.conditionList 里(单元/人群层同一个坑,
    放顶层被忽略回上层汇总); 不给 adgroupIdList —— 按 crowd 层同构预期一次回全计划词行,
    以探针产物为准。"""
    return {
        "offset": offset, "pageSize": page_size, "orderField": "", "orderBy": "",
        "bizCode": biz_code, "mx_bizCode": biz_code,
        "campaignIdList": [str(campaign_id)],
        "rptQuery": {"fields": FIELDS_STR, "conditionList": [{
            "sourceList": ["adgroup_detail", "word_list"],
            "startTime": day, "endTime": day, "isRt": False}]},
        "csrfId": tpl["body"].get("csrfId"),
        "loginPointId": tpl["body"].get("loginPointId"),
    }


def word_of(word_row):
    """词行的 (词id, 词文本)。字段名以探针产物为准 —— 这里的候选链按「与 crowd 同构」
    的预期写的; 探针若发现平台用的别的名字, 只改这里(单测 fixture 同步改)。"""
    wid = word_row.get("bidwordId") or word_row.get("wordId") or ""
    w = word_row.get("word") or (word_row.get("bidword") or {}).get("word") \
        or (word_row.get("keyword") or {}).get("word") or ""
    return str(wid), w
```

(e) `map_crowd_row`（L245-288）之后加 `map_word_row`：

```python
def map_word_row(word_row, adgroup, stat_date, shop_id, plan_type, report_source):
    """一个 (单元,词) 节点 → 一行 promo_cost_item_daily。

    entity_key 必须 "<adgroupId>:<词文本>" —— 同一个词会被多个单元共用(计划级词库),
    光用词文本做键, 两个单元的同名词行会在唯一键 (shop_id, dimension, entity_key,
    campaign_id, stat_date) 上互踩、upsert 互相覆盖。复合模式对齐 crowd 行的
    "<adgroupId>:<crowdId>"。词 id 平台侧有就存 entity_id, 没有留空串(表注释已说明
    「关键词本身没有 id」)。item_id 只能从单元层 join 回来: 词行不带 material。
    """
    rl = word_row.get("reportInfoList")
    info = rl[0] if isinstance(rl, list) and rl else None
    if not isinstance(info, dict) or "charge" not in info:
        return None, "no_data"
    cid = word_row.get("campaignId") or adgroup.get("campaignId")
    if cid is None:
        return None, "no_campaign"
    wid, word = word_of(word_row)
    if not word:
        return None, "no_word"
    unit_id = str(word_row.get("adgroupId") or adgroup.get("adgroupId") or "")
    item_id = item_id_of(adgroup)
    if not item_id:
        return None, "no_item_id"
    title = adgroup.get("adgroupName")
    row = {
        "shop_id": shop_id if shop_id is not None else 0,
        "platform_code": PLATFORM_CODE,
        "stat_date": stat_date,
        "plan_type": plan_type,
        "dimension": "keyword",
        "entity_key": f"{unit_id}:{word}",
        "entity_id": wid,
        "entity_name": word,
        "item_id": item_id,
        "item_name": title,
        "campaign_id": str(cid),
        "campaign_name": adgroup.get("campaignName"),
        "unit_id": unit_id,
        "unit_name": title,
        "report_source": report_source,
        "raw_json": json.dumps(word_row, ensure_ascii=False),
    }
    for src, col, kind in FIELD_MAP:
        row[col] = cast(info.get(src), kind)
    return row, None
```

- [ ] **Step 4: 跑测试确认绿**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python test_alimama_map.py
```
Expected: `OK: collect_alimama_promo 纯函数全部断言通过`。

- [ ] **Step 5: 实现 fetch/collect 与 run() 接线**

(a) `fetch_crowds`（L434-441）之后加：

```python
async def fetch_words(page, tpl, biz_code, campaign_id, day, offset, page_size):
    body = word_body(tpl, biz_code, campaign_id, day, offset, page_size)
    url = WORD_URL + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=" + biz_code
    r = await page.evaluate("""async ([u, h, b]) => {
        const res = await fetch(u, {method:'POST', headers:h, body:JSON.stringify(b), credentials:'include'});
        return {status: res.status, text: await res.text()};
    }""", [url, tpl["headers"], body])
    return r["status"], r["text"]


async def collect_words(page, tpl, biz_code, campaign_id, day, adgroup_by_id, plan_type, args):
    """按计划采一次词层(与人群层同构: 不给 adgroupIdList → 一次回全计划词行, 以探针为准)。

    adgroup_by_id 里没有的单元跳过：拿不到 material → 没有 item_id，落了也 join 不上商品。
    """
    rows, seen, offset, pages = [], 0, 0, 0
    while pages < MAX_PAGES:
        status, text = await fetch_words(page, tpl, biz_code, campaign_id, day,
                                         offset, args.word_page_size)
        if hit_risk(text):
            log(f"!! 词层 {day} 计划{campaign_id} 命中风控")
            break
        try:
            j = json.loads(text)
        except Exception:
            log(f"  词层非 JSON 响应 HTTP {status} offset={offset}")
            break
        data = j.get("data") or {}
        lst = data.get("list") or []
        seen += len(lst)
        for wr in lst:
            adg = adgroup_by_id.get(str(wr.get("adgroupId") or ""))
            if adg is None:
                continue
            row, _reason = map_word_row(wr, adg, day, args.shop_id, plan_type,
                                        f"alimama-keyword:{biz_code}")
            if row is not None:
                rows.append(row)
        with open(os.path.join(RAW_DIR, f"words_{campaign_id}_{day}_{offset}.json"), "w",
                  encoding="utf-8") as f:
            f.write(text)
        pages += 1
        count = data.get("count") or seen
        if offset + args.word_page_size >= int(count) or not lst:
            break
        offset += args.word_page_size
        await asyncio.sleep(args.gap)
    return rows, seen, pages
```

(b) `run()` 里人群层块（原 L639-655）。**把 `by_id` 的构建从人群块里挪出来放在两个块之前**（词层共用），然后在人群块之后、该循环尾部的 `await asyncio.sleep(args.gap)` 之前插入词层块：

```python
                        by_id = {str(a.get("adgroupId")): a for a in adgroups
                                 if a.get("adgroupId") is not None}
                        # 人群层：只对白名单计划（默认 #1 关键词标准），且要采人群的 level
                        if wants_crowd(args.level) and str(cid) in crowd_cids:
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
                        # 词层：只对白名单计划（默认 84290744044 reprice 对象），且要采词的 level
                        if wants_word(args.level) and str(cid) in word_cids:
                            word_rows, wseen, wpages = await collect_words(
                                page, tpl, biz_code, cid, day, by_id, plan_type, args)
                            for r in word_rows:
                                r["import_batch"] = batch_tag
                            if word_rows:
                                if args.dry_run:
                                    item_ok += len(word_rows)
                                else:
                                    item_ok += upsert(conn, "promo_cost_item_daily", ITEM_COLS,
                                                      word_rows, batch_tag)
                            item_total += wseen
                            log(f"    词 {cid}: 有数{len(word_rows)}/{wseen} 页{wpages}")
                        await asyncio.sleep(args.gap)
```

（注意：词层与人群层共用同一份 `ITEM_COLS` upsert 与同一个 `promo_cost_detail` 台账批次——**不新增 begin_batch**。）

(c) `run()` 开头白名单解析区（原 L533-536）加：

```python
    word_cids = {s.strip() for s in (args.word_campaign_ids or "").split(",") if s.strip()}
```

并把 L536 的 log 行改为同时打印词层白名单：

```python
    log(f"人群层白名单 {sorted(crowd_cids)}；词层白名单 {sorted(word_cids)}；单元级强制包含 {sorted(include_cids)}")
```

(d) `main()` 参数区（L716-723）：`--level` choices 加 `"word"`（help 同步说明 word=计划+宝贝+词），并新增两个参数（`--crowd-campaign-ids` 默认值**保持 `83392643008` 不动**）：

```python
    ap.add_argument("--level", choices=("campaign", "item", "crowd", "word", "both", "all"),
                    default="campaign",
                    help="campaign=只采计划日报 item/both=计划+宝贝 crowd=计划+宝贝+人群 "
                         "word=计划+宝贝+词 all=全部")
    ap.add_argument("--word-campaign-ids", default="84290744044",
                    help="只对这些计划采词层(逗号分隔); 默认 84290744044(reprice 对象)")
    ap.add_argument("--word-page-size", type=int, default=500, help="词层分页大小")
```

- [ ] **Step 6: 冒烟**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python test_alimama_map.py && ../venv/bin/python collect_alimama_promo.py --help | grep -A1 word
```
Expected: 断言全过 + help 里出现 `--word-campaign-ids`。

- [ ] **Step 7: 改 cron shell 命令行（唯一真相）**

`cron_alimama_promo.sh` L44-47 改为（只改采集命令与其上一行日志文案；其余守卫/告警逻辑不动）：

```bash
echo "[$(date '+%F %T')] 开始采集（滚动 ${DAYS} 天，计划+宝贝+人群+词四层）" >> "$LOG"
$PY collect_alimama_promo.py --level all --days "$DAYS" --gap 4 \
  --crowd-campaign-ids 83392643008,84290744044 \
  --word-campaign-ids 84290744044 \
  --include-campaign-ids 83949710619,83340870410 >> "$LOG" 2>&1
```

Expected: `bash -n cron_alimama_promo.sh` 无输出（语法 OK）。

---

### Task 3: 首采 30 天回补 + 数据校验

**Files:** 无新文件（跑现有采集器 + SQL 校验）。

**Interfaces:**
- Consumes: Task 2 的采集器词层。
- Produces: `promo_cost_item_daily` 里 84290744044 近 30 天词行（约 1.2-1.5 万行）——Task 5/6/8 的数据基础。

- [ ] **Step 1: dry-run 一天验证（不写库不进台账）**

执行时机遵守 9222 红线（Global Constraints）。

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
../venv/bin/python collect_alimama_promo.py --level word --days 1 --gap 3 --dry-run
```
Expected: 日志出现 `词 84290744044: 有数 N 行/M 页` 且 N>0。N=0 → 先看 `alimama_promo_raw/words_*.json` 响应体：若是「接口通了但字段名对不上」回 Task 2 修 `word_of`；若是「接口回的是汇总不是词×单元粒度」→ 按 spec §9.5 找用户谈降级。

- [ ] **Step 2: 真跑 30 天回补（后台长跑）**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
nohup ../venv/bin/python collect_alimama_promo.py --level word --days 30 --gap 4 \
  > /tmp/promo_word_backfill.log 2>&1 &
```
预计 30 天 × 每天计划层 1 发 + 单元层若干页 + 词层 1-2 发 ≈ 半小时级。周期性 `tail /tmp/promo_word_backfill.log` 看进度与风控关键字（`RGV587` 等；命中风控会自停，冷却后重跑即可——30 天窗口有 upsert 幂等，重复跑无害）。

- [ ] **Step 3: 落库规模核对**

```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT stat_date, COUNT(*) kw_rows, COUNT(DISTINCT unit_id) units
FROM promo_cost_item_daily
WHERE dimension='keyword' AND campaign_id='84290744044'
GROUP BY stat_date ORDER BY stat_date DESC LIMIT 35;"
```
Expected: 约 30 行（有投放的天），每行 kw_rows 几百内、units ≤ 67。

- [ ] **Step 4: entity_key 复合唯一性核对**

```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT unit_id, entity_name, stat_date, COUNT(*) c FROM promo_cost_item_daily
WHERE dimension='keyword' AND campaign_id='84290744044'
GROUP BY unit_id, entity_name, stat_date HAVING c>1 LIMIT 10;"
```
Expected: 空结果（有行=同词同单元同天被写成多行，键逻辑有 bug，回 Task 2）。

- [ ] **Step 5: Σ词点击 vs 单元点击核对（词层完整性）**

```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT s.stat_date, s.unit_click, k.kw_click,
       ROUND(k.kw_click / NULLIF(s.unit_click, 0) * 100, 1) pct
FROM (SELECT stat_date, unit_id, SUM(click) unit_click FROM promo_cost_item_daily
      WHERE dimension='item' AND campaign_id='84290744044' GROUP BY stat_date, unit_id) s
JOIN (SELECT stat_date, unit_id, SUM(click) kw_click FROM promo_cost_item_daily
      WHERE dimension='keyword' AND campaign_id='84290744044' GROUP BY stat_date, unit_id) k
  ON k.stat_date = s.stat_date AND k.unit_id = s.unit_id
ORDER BY s.stat_date DESC LIMIT 40;"
```
Expected: pct 普遍接近 100%（词流量应占单元绝大部分；个别偏离记下来汇报用户，不阻塞——可能是平台归因口径差，与采集器里「宝贝合计 vs 计划花费」的 drift 同性质）。

- [ ] **Step 6: 台账确认**

```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT id, dataset, status, rows_ok, biz_from, biz_to, finished_at
FROM ingest_batch WHERE dataset='promo_cost_detail' ORDER BY id DESC LIMIT 3;"
```
Expected: 最新一条 `promo_cost_detail` 批次 status=success（或 partial 且 error 只是归因偏差注记）、rows_ok 覆盖词行数。

---

### Task 4: 后端 VO（spzx-model）

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/promo/PromoUnitVo.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/promo/PromoUnitTrendVo.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/promo/PromoUnitKeywordVo.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/promo/PromoUnitCrowdVo.java`

**Interfaces:**
- Produces: 四个 VO 供 Task 5（XML resultType）与 Task 6（service/controller）使用。字段名即 MyBatis 驼峰映射名，XML 别名必须与之一致。

- [ ] **Step 1: 写四个 VO（全文如下）**

`PromoUnitVo.java`：

```java
package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 单元维度推广区间聚合（推广·单元日报页）。
 * 占比不在 SQL 里算 —— SQL 只出分子 crowdClick 与分母 click，service 先加总再除。
 */
@Data
@Schema(description = "单元维度推广区间聚合")
public class PromoUnitVo {

    private String unitId;
    @Schema(description = "单元名（关键词推广里单元=宝贝，即商品标题）")
    private String unitName;
    private String campaignId;
    private String campaignName;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
    private BigDecimal charge;
    private Long adPv;
    private Long click;
    private BigDecimal ctrPercent;
    private BigDecimal cpc;
    private BigDecimal gmvTotal;
    private Integer orderTotal;
    private BigDecimal roi;
    private Integer cartCount;
    private Integer collectTotal;
    @Schema(description = "该单元各人群点击之和（只有采了人群层的计划有值）；null=没有人群数据")
    private Long crowdClick;
    @Schema(description = "人群点击占比 = 人群点击 / 总点击 × 100（百分数）；click=0 或无人群数据为 null")
    private BigDecimal crowdClickShare;
}
```

`PromoUnitTrendVo.java`：

```java
package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元逐日趋势（各维度随时间变化，前端勾选画线）。 */
@Data
@Schema(description = "单元逐日趋势")
public class PromoUnitTrendVo {

    @Schema(description = "统计日 yyyy-MM-dd")
    private String statDate;
    private BigDecimal charge;
    private Long adPv;
    private Long click;
    private BigDecimal ctrPercent;
    private BigDecimal cpc;
    private BigDecimal gmvTotal;
    private Integer orderTotal;
    private BigDecimal roi;
    private Integer cartCount;
    private Integer collectTotal;
    private Long crowdClick;
    @Schema(description = "逐日人群点击占比（百分数）")
    private BigDecimal crowdClickShare;
}
```

`PromoUnitKeywordVo.java`：

```java
package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元 × 关键词明细（词层报表，dimension='keyword'）。 */
@Data
@Schema(description = "单元关键词明细")
public class PromoUnitKeywordVo {

    @Schema(description = "关键词文本")
    private String keyword;
    @Schema(description = "平台词 id（平台没给就为 null）")
    private String bidwordId;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
    private BigDecimal charge;
    private Long click;
    @Schema(description = "平均点击单价")
    private BigDecimal cpc;
    private BigDecimal gmvTotal;
    private Integer orderTotal;
    private BigDecimal roi;
    private Integer cartCount;
    private Integer collectTotal;
}
```

`PromoUnitCrowdVo.java`：

```java
package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元 × 人群明细（dimension='crowd'）。占比 = 该人群点击 / 该单元总点击。 */
@Data
@Schema(description = "单元人群明细")
public class PromoUnitCrowdVo {

    private String crowdId;
    private String crowdName;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
    private Long click;
    private BigDecimal charge;
    @Schema(description = "该单元区间总点击（每行都带，供 service 算占比）")
    private Long unitClick;
    @Schema(description = "人群点击占比 = click / unitClick × 100（百分数）；unitClick=0 为 null")
    private BigDecimal crowdClickShare;
}
```

- [ ] **Step 2: 编译 install model**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
# workdir: /Users/qyk9527/ideaProject/spzx-parent
mvn install -pl spzx-model -DskipTests -q
```
Expected: BUILD SUCCESS（静默）。

---

### Task 5: 后端 Mapper + XML（四条只读 SQL）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/PromoUnitMapper.java`
- Create: `spzx-manager/src/main/resources/mapper/PromoUnitMapper.xml`

**Interfaces:**
- Consumes: Task 4 的四个 VO。
- Produces: `PromoUnitMapper` 四个方法（Task 6 注入调用）。无分页（67 单元/463 词规模一页够）；比率列全部 `NULLIF` 出 NULL；本四条 SQL **都不 join `promo_plan`**（campaign_name 直接取明细行），无 COLLATE 坑。

- [ ] **Step 1: 写 Mapper 接口（全文）**

```java
package com.joker.spzx.manager.mapper;

import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/** 推广·单元日报只读聚合。全部走 promo_cost_item_daily 明细表按 unit 聚合。 */
@Mapper
public interface PromoUnitMapper {

    List<PromoUnitVo> selectUnits(@Param("dateFrom") String dateFrom,
                                  @Param("dateTo") String dateTo,
                                  @Param("campaignId") String campaignId,
                                  @Param("sort") String sort);

    List<PromoUnitTrendVo> selectUnitTrend(@Param("dateFrom") String dateFrom,
                                           @Param("dateTo") String dateTo,
                                           @Param("campaignId") String campaignId,
                                           @Param("unitId") String unitId);

    List<PromoUnitKeywordVo> selectUnitKeywords(@Param("dateFrom") String dateFrom,
                                                @Param("dateTo") String dateTo,
                                                @Param("campaignId") String campaignId,
                                                @Param("unitId") String unitId,
                                                @Param("sort") String sort);

    List<PromoUnitCrowdVo> selectUnitCrowds(@Param("dateFrom") String dateFrom,
                                            @Param("dateTo") String dateTo,
                                            @Param("campaignId") String campaignId,
                                            @Param("unitId") String unitId);
}
```

- [ ] **Step 2: 写 XML（全文）**

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN"
        "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.joker.spzx.manager.mapper.PromoUnitMapper">

    <!-- 推广·单元日报：全部只读聚合 promo_cost_item_daily。
         纪律（同 PromoReportMapper）：
         1) 比率一律用汇总后的分子分母重算，SQL 里 NULLIF 出 NULL，不粉饰成 0；
            占比(crowdClickShare)连 SQL 都不算 —— 只出分子 crowdClick 与分母 click，service 先加总再除。
         2) 四条 SQL 都不 join promo_plan（campaign_name 就在明细行上），无 COLLATE 坑。
         3) 排序只走 <choose> 白名单，不拼接 —— 天然防注入。 -->
    <select id="selectUnits" resultType="com.joker.spzx.model.vo.promo.PromoUnitVo">
        SELECT i.unit_id                                                     AS unitId,
               MAX(i.unit_name)                                              AS unitName,
               MAX(i.campaign_id)                                            AS campaignId,
               MAX(i.campaign_name)                                          AS campaignName,
               COUNT(DISTINCT i.stat_date)                                   AS days,
               ROUND(SUM(i.charge), 2)                                       AS charge,
               SUM(i.ad_pv)                                                  AS adPv,
               SUM(i.click)                                                  AS click,
               ROUND(SUM(i.click) / NULLIF(SUM(i.ad_pv), 0) * 100, 4)         AS ctrPercent,
               ROUND(SUM(i.charge) / NULLIF(SUM(i.click), 0), 4)              AS cpc,
               ROUND(SUM(i.gmv_total), 2)                                    AS gmvTotal,
               SUM(i.order_total)                                            AS orderTotal,
               ROUND(SUM(i.gmv_total) / NULLIF(SUM(i.charge), 0), 2)          AS roi,
               SUM(i.cart_count)                                             AS cartCount,
               SUM(i.collect_total)                                          AS collectTotal,
               MAX(cc.crowd_click)                                           AS crowdClick
        FROM promo_cost_item_daily i
                 LEFT JOIN (SELECT c.unit_id, SUM(c.click) AS crowd_click
                            FROM promo_cost_item_daily c
                            WHERE c.dimension = 'crowd'
                              AND c.stat_date BETWEEN #{dateFrom} AND #{dateTo}
                              AND c.campaign_id = #{campaignId}
                            GROUP BY c.unit_id) cc ON cc.unit_id = i.unit_id
        WHERE i.dimension = 'item'
          AND i.campaign_id = #{campaignId}
          AND i.stat_date BETWEEN #{dateFrom} AND #{dateTo}
        GROUP BY i.unit_id
        <choose>
            <when test="sort == 'click'">ORDER BY click IS NULL, click DESC</when>
            <when test="sort == 'roi'">ORDER BY roi IS NULL, roi DESC</when>
            <when test="sort == 'gmv'">ORDER BY gmvTotal IS NULL, gmvTotal DESC</when>
            <when test="sort == 'crowdClick'">ORDER BY crowdClick IS NULL, crowdClick DESC</when>
            <otherwise>ORDER BY charge IS NULL, charge DESC</otherwise>
        </choose>
    </select>

    <select id="selectUnitTrend" resultType="com.joker.spzx.model.vo.promo.PromoUnitTrendVo">
        SELECT i.stat_date                                                   AS statDate,
               ROUND(SUM(i.charge), 2)                                       AS charge,
               SUM(i.ad_pv)                                                  AS adPv,
               SUM(i.click)                                                  AS click,
               ROUND(SUM(i.click) / NULLIF(SUM(i.ad_pv), 0) * 100, 4)         AS ctrPercent,
               ROUND(SUM(i.charge) / NULLIF(SUM(i.click), 0), 4)              AS cpc,
               ROUND(SUM(i.gmv_total), 2)                                    AS gmvTotal,
               SUM(i.order_total)                                            AS orderTotal,
               ROUND(SUM(i.gmv_total) / NULLIF(SUM(i.charge), 0), 2)          AS roi,
               SUM(i.cart_count)                                             AS cartCount,
               SUM(i.collect_total)                                          AS collectTotal,
               MAX(cc.crowd_click)                                           AS crowdClick
        FROM promo_cost_item_daily i
                 LEFT JOIN (SELECT c.stat_date, SUM(c.click) AS crowd_click
                            FROM promo_cost_item_daily c
                            WHERE c.dimension = 'crowd'
                              AND c.stat_date BETWEEN #{dateFrom} AND #{dateTo}
                              AND c.campaign_id = #{campaignId}
                              AND c.unit_id = #{unitId}
                            GROUP BY c.stat_date) cc ON cc.stat_date = i.stat_date
        WHERE i.dimension = 'item'
          AND i.campaign_id = #{campaignId}
          AND i.unit_id = #{unitId}
          AND i.stat_date BETWEEN #{dateFrom} AND #{dateTo}
        GROUP BY i.stat_date
        ORDER BY i.stat_date
    </select>

    <select id="selectUnitKeywords" resultType="com.joker.spzx.model.vo.promo.PromoUnitKeywordVo">
        SELECT MAX(i.entity_name)                                            AS keyword,
               MAX(i.entity_id)                                              AS bidwordId,
               COUNT(DISTINCT i.stat_date)                                   AS days,
               ROUND(SUM(i.charge), 2)                                       AS charge,
               SUM(i.click)                                                  AS click,
               ROUND(SUM(i.charge) / NULLIF(SUM(i.click), 0), 4)              AS cpc,
               ROUND(SUM(i.gmv_total), 2)                                    AS gmvTotal,
               SUM(i.order_total)                                            AS orderTotal,
               ROUND(SUM(i.gmv_total) / NULLIF(SUM(i.charge), 0), 2)          AS roi,
               SUM(i.cart_count)                                             AS cartCount,
               SUM(i.collect_total)                                          AS collectTotal
        FROM promo_cost_item_daily i
        WHERE i.dimension = 'keyword'
          AND i.campaign_id = #{campaignId}
          AND i.unit_id = #{unitId}
          AND i.stat_date BETWEEN #{dateFrom} AND #{dateTo}
        GROUP BY i.entity_name
        <choose>
            <when test="sort == 'click'">ORDER BY click IS NULL, click DESC</when>
            <when test="sort == 'roi'">ORDER BY roi IS NULL, roi DESC</when>
            <when test="sort == 'gmv'">ORDER BY gmvTotal IS NULL, gmvTotal DESC</when>
            <otherwise>ORDER BY charge IS NULL, charge DESC</otherwise>
        </choose>
    </select>

    <!-- 人群行按 entity_key 分组（"<adgroupId>:<crowdId>" 已含单元，单元内天然唯一）；
         unitClick 用标量子查询带在每行上（同单元每行相同），占比由 service 统一算。 -->
    <select id="selectUnitCrowds" resultType="com.joker.spzx.model.vo.promo.PromoUnitCrowdVo">
        SELECT MAX(i.entity_id)                                              AS crowdId,
               MAX(i.entity_name)                                            AS crowdName,
               COUNT(DISTINCT i.stat_date)                                   AS days,
               SUM(i.click)                                                  AS click,
               ROUND(SUM(i.charge), 2)                                       AS charge,
               (SELECT SUM(x.click) FROM promo_cost_item_daily x
                 WHERE x.dimension = 'item'
                   AND x.campaign_id = #{campaignId}
                   AND x.unit_id = #{unitId}
                   AND x.stat_date BETWEEN #{dateFrom} AND #{dateTo})         AS unitClick
        FROM promo_cost_item_daily i
        WHERE i.dimension = 'crowd'
          AND i.campaign_id = #{campaignId}
          AND i.unit_id = #{unitId}
          AND i.stat_date BETWEEN #{dateFrom} AND #{dateTo}
        GROUP BY i.entity_key
        ORDER BY click IS NULL, click DESC
    </select>
</mapper>
```

- [ ] **Step 3: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
# workdir: /Users/qyk9527/ideaProject/spzx-parent
mvn compile -pl spzx-manager -am -q
```
Expected: BUILD SUCCESS。XML 正确性（SQL 语法/别名映射）在 Task 6 单测+Task 9 端到端验证。

---

### Task 6: 后端 Service + Controller + 单测

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/promo/PromoUnitService.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/PromoUnitController.java`
- Test: `spzx-manager/src/test/java/com/joker/spzx/manager/service/promo/PromoUnitServiceTest.java`

**Interfaces:**
- Consumes: Task 5 的 `PromoUnitMapper`；`PromoReportService.normalizeRange`（static，同包可调；若编译报不可见就把它和 `normalizeChoice` 提为 `public static`，行为不变）。
- Produces: REST 端点 `GET /admin/promo/unit/units|trend|keywords|crowds`（Task 7/8 前端调用；Task 9 一致性门核对）。占比公式只此一份（私有 `pct`），三个 apply 都调它。

- [ ] **Step 1: 写失败单测（先写测试）**

`PromoUnitServiceTest.java` 全文：

```java
package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 单元日报的纯函数：占比先加总再除（分子分母在 SQL 已汇总好）、分母 0 出 null、
 * 缺省区间止于昨天。纯 JUnit，不拉 Spring。
 */
class PromoUnitServiceTest {

    @Test
    void 人群占比先加总再除且分母为0出null() {
        PromoUnitVo v = new PromoUnitVo();
        v.setClick(10L);
        v.setCrowdClick(3L);
        PromoUnitService.applyCrowdShare(v);
        assertEquals(0, new java.math.BigDecimal("30.00").compareTo(v.getCrowdClickShare()));
        v.setClick(0L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
    }

    @Test
    void 人群占比分子或分母缺失出null() {
        PromoUnitVo v = new PromoUnitVo();
        v.setClick(10L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
        v.setClick(null);
        v.setCrowdClick(3L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
    }

    @Test
    void 趋势行占比同口径() {
        PromoUnitTrendVo t = new PromoUnitTrendVo();
        t.setClick(8L);
        t.setCrowdClick(5L);
        PromoUnitService.applyTrendShare(t);
        assertEquals(0, new java.math.BigDecimal("62.50").compareTo(t.getCrowdClickShare()));
    }

    @Test
    void 人群行占比按单元总点击算且总点击缺失出null() {
        PromoUnitCrowdVo c = new PromoUnitCrowdVo();
        c.setClick(3L);
        c.setUnitClick(10L);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertEquals(0, new java.math.BigDecimal("30.00").compareTo(c.getCrowdClickShare()));
        c.setUnitClick(0L);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertNull(c.getCrowdClickShare());
        c.setUnitClick(null);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertNull(c.getCrowdClickShare());
    }

    @Test
    void 缺省区间止于昨天而不是今天() {
        String[] r = PromoReportService.normalizeRange(null, null, LocalDate.of(2026, 10, 18));
        assertEquals("2026-10-04", r[0]);
        assertEquals("2026-10-17", r[1]);
    }
}
```

- [ ] **Step 2: 跑测试确认红**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
# workdir: /Users/qyk9527/ideaProject/spzx-parent
mvn test -pl spzx-manager -am -Dtest='PromoUnitServiceTest' -Dsurefire.failIfNoSpecifiedTests=false
```
Expected: 编译失败（`PromoUnitService` 不存在）。

- [ ] **Step 3: 写 Service（全文）**

```java
package com.joker.spzx.manager.service.promo;

import com.joker.spzx.manager.mapper.PromoUnitMapper;
import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;

/**
 * 推广·单元日报（只读下钻，spec 2026-10-18-promo-unit-daily-design）。
 *
 * 占比公式全服务只有 pct() 这一份：分子分母都已在 SQL 里按区间汇总好，这里只做除法 ——
 * 「先加总再除」「分母 0 出 NULL 不粉饰成 0」与 PromoReportService.applyCrowdShare 同一条纪律，
 * 但作用在不同 VO 上，各自有单测钉住。
 */
@Service
public class PromoUnitService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    @Autowired
    private PromoUnitMapper promoUnitMapper;

    public List<PromoUnitVo> units(String from, String to, String campaignId, String sort) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitVo> list = promoUnitMapper.selectUnits(r[0], r[1], campaignId.trim(), sort);
        list.forEach(PromoUnitService::applyCrowdShare);
        return list;
    }

    public List<PromoUnitTrendVo> trend(String from, String to, String campaignId, String unitId) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitTrendVo> list =
                promoUnitMapper.selectUnitTrend(r[0], r[1], campaignId.trim(), unitId.trim());
        list.forEach(PromoUnitService::applyTrendShare);
        return list;
    }

    public List<PromoUnitKeywordVo> keywords(String from, String to, String campaignId, String unitId,
                                             String sort) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        return promoUnitMapper.selectUnitKeywords(r[0], r[1], campaignId.trim(), unitId.trim(), sort);
    }

    public List<PromoUnitCrowdVo> crowds(String from, String to, String campaignId, String unitId) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitCrowdVo> list =
                promoUnitMapper.selectUnitCrowds(r[0], r[1], campaignId.trim(), unitId.trim());
        list.forEach(PromoUnitService::applyCrowdShareToUnitClick);
        return list;
    }

    static void applyCrowdShare(PromoUnitVo vo) {
        vo.setCrowdClickShare(pct(vo.getCrowdClick(), vo.getClick()));
    }

    static void applyTrendShare(PromoUnitTrendVo vo) {
        vo.setCrowdClickShare(pct(vo.getCrowdClick(), vo.getClick()));
    }

    static void applyCrowdShareToUnitClick(PromoUnitCrowdVo vo) {
        vo.setCrowdClickShare(pct(vo.getClick(), vo.getUnitClick()));
    }

    private static BigDecimal pct(Long num, Long den) {
        if (num == null || den == null || den == 0) {
            return null;
        }
        return BigDecimal.valueOf(num).multiply(HUNDRED)
                .divide(BigDecimal.valueOf(den), 2, RoundingMode.HALF_UP);
    }
}
```

- [ ] **Step 4: 写 Controller（全文）**

```java
package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.promo.PromoUnitService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 推广·单元日报（只读）。campaignId 必填（页面计划下拉），unitId 除 units 外必填。 */
@RestController
@Tag(name = "推广单元日报", description = "万相台标准计划单元级只读下钻（关键词明细/人群点击占比）")
@RequestMapping("/admin/promo/unit")
public class PromoUnitController {

    @Autowired
    private PromoUnitService promoUnitService;

    @Operation(summary = "单元列表（占比=人群点击/总点击，先加总再除，分母0出null）")
    @GetMapping("/units")
    public Result<List<PromoUnitVo>> units(@RequestParam String campaignId,
                                           @RequestParam(required = false) String from,
                                           @RequestParam(required = false) String to,
                                           @RequestParam(required = false, defaultValue = "charge") String sort) {
        return Result.build(promoUnitService.units(from, to, campaignId, sort));
    }

    @Operation(summary = "单元逐日全指标趋势（含逐日人群占比）")
    @GetMapping("/trend")
    public Result<List<PromoUnitTrendVo>> trend(@RequestParam String campaignId,
                                                @RequestParam String unitId,
                                                @RequestParam(required = false) String from,
                                                @RequestParam(required = false) String to) {
        return Result.build(promoUnitService.trend(from, to, campaignId, unitId));
    }

    @Operation(summary = "单元关键词明细（词/点击/均价/花费/收藏/加购/成交单数/成交金额/ROI）")
    @GetMapping("/keywords")
    public Result<List<PromoUnitKeywordVo>> keywords(@RequestParam String campaignId,
                                                     @RequestParam String unitId,
                                                     @RequestParam(required = false) String from,
                                                     @RequestParam(required = false) String to,
                                                     @RequestParam(required = false, defaultValue = "charge") String sort) {
        return Result.build(promoUnitService.keywords(from, to, campaignId, unitId, sort));
    }

    @Operation(summary = "单元人群明细（含人群点击占比与差额=泛流量口径）")
    @GetMapping("/crowds")
    public Result<List<PromoUnitCrowdVo>> crowds(@RequestParam String campaignId,
                                                 @RequestParam String unitId,
                                                 @RequestParam(required = false) String from,
                                                 @RequestParam(required = false) String to) {
        return Result.build(promoUnitService.crowds(from, to, campaignId, unitId));
    }
}
```

- [ ] **Step 5: 跑单测确认绿**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
# workdir: /Users/qyk9527/ideaProject/spzx-parent
mvn test -pl spzx-manager -am -Dtest='PromoUnitServiceTest' -Dsurefire.failIfNoSpecifiedTests=false
```
Expected: `Tests run: 5, Failures: 0, Errors: 0`。

---

### Task 7: 前端 api + 路由

**Files:**
- Create: `webstormProject/spzx-admin/src/api/promoUnit.js`
- Modify: `webstormProject/spzx-admin/src/router/modules/mall.js`（import 区 + promoReport 路由块之后）

**Interfaces:**
- Consumes: Task 6 的 4 个端点。
- Produces: 4 个 api 函数（Task 8 页面 import）+ 路由 `/promoUnit`。

- [ ] **Step 1: 写 api 文件（全文）**

```js
import request from '@/utils/request'

const api_name = '/admin/promo/unit'

// campaignId 必填（页面计划下拉）；from/to 不传即「昨天往前 14 天」
export const GetPromoUnits = query => {
  return request({
    url: `${api_name}/units`,
    method: 'get',
    params: query,
    silent: true,
  })
}

export const GetPromoUnitTrend = query => {
  return request({
    url: `${api_name}/trend`,
    method: 'get',
    params: query,
    silent: true,
  })
}

// sort: charge|click|gmv|roi
export const GetPromoUnitKeywords = query => {
  return request({
    url: `${api_name}/keywords`,
    method: 'get',
    params: query,
    silent: true,
  })
}

export const GetPromoUnitCrowds = query => {
  return request({
    url: `${api_name}/crowds`,
    method: 'get',
    params: query,
    silent: true,
  })
}
```

- [ ] **Step 2: 注册路由**

`mall.js` import 区（`const promoReport = ...` 旁边）加：

```js
const promoUnit = () => import('@/views/mall/promoUnit.vue')
```

promoReport 路由块（原 191-199 行）之后插入：

```js
      {
        path: '/promoUnit',
        name: 'promoUnit',
        component: promoUnit,
        meta: {
          title: '单元日报',
        },
        hidden: false,
      },
```

- [ ] **Step 3: 冒烟**

```bash
# workdir: /Users/qyk9527/webstormProject/spzx-admin
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/api/promoUnit.js','utf8'),{sourceType:'module'})" 2>/dev/null || node --check src/api/promoUnit.js 2>/dev/null || echo "语法检查跳过（dev 构建时验证）"
grep -n "promoUnit" src/router/modules/mall.js
```
Expected: grep 输出 import 行与路由块两处。

---

### Task 8: 前端页面 promoUnit.vue

**Files:**
- Create: `webstormProject/spzx-admin/src/views/mall/promoUnit.vue`

**Interfaces:**
- Consumes: Task 7 的 4 个 api 函数；Task 6 端点字段（VO 驼峰名）。
- 交互定型（owner 已确认）：工具栏（计划下拉默认 84290744044 + 日期区间默认近 14 天）→ 单元表（可排序，人群占比列着色）→ 点行展开单元详情（趋势 echarts 维度勾选 + 关键词/人群两个 tab）。词表无数据时显示「词级明细待采集」占位，不报错。

- [ ] **Step 1: 写页面（全文）**

```vue
<template>
  <div class="app-main-container">
    <el-card shadow="never" class="toolbar">
      <div class="toolbar-row">
        <el-select v-model="campaignId" filterable style="width: 320px" @change="reload">
          <el-option v-for="p in plans" :key="p.campaignId" :value="p.campaignId"
                     :label="`${p.campaignName}（${p.campaignId}）`" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                        range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期"
                        :clearable="false" :disabled-date="futureDate" style="width: 260px"
                        @change="reload" />
        <span class="hint">人群占比 = 人群命中点击 ÷ 单元总点击，差额为泛流量（不在任何人群上的点击）</span>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table :data="units" v-loading="loading" row-key="unitId"
                @expand-change="onExpand" :expand-row-keys="expandedKeys">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail" v-loading="row._detailLoading">
              <el-tabs v-model="row._tab">
                <el-tab-pane label="趋势" name="trend">
                  <div class="metric-pick">
                    <el-checkbox-group v-model="row._metrics" @change="drawTrend(row)">
                      <el-checkbox v-for="m in METRICS" :key="m.key" :value="m.key">{{ m.label }}</el-checkbox>
                    </el-checkbox-group>
                  </div>
                  <div :ref="el => setChartRef(row.unitId, el)" class="trend-chart" />
                </el-tab-pane>
                <el-tab-pane label="关键词" name="kw">
                  <el-table :data="row._keywords" size="small" max-height="420">
                    <el-table-column prop="keyword" label="关键词" min-width="160" show-overflow-tooltip />
                    <el-table-column prop="charge" label="花费" width="90" sortable />
                    <el-table-column prop="click" label="点击量" width="90" sortable />
                    <el-table-column prop="cpc" label="均价" width="90" sortable />
                    <el-table-column prop="collectTotal" label="收藏" width="80" />
                    <el-table-column prop="cartCount" label="加购" width="80" />
                    <el-table-column prop="orderTotal" label="成交单数" width="95" sortable />
                    <el-table-column prop="gmvTotal" label="成交金额" width="100" sortable />
                    <el-table-column prop="roi" label="投产比" width="90" sortable />
                  </el-table>
                  <div v-if="row._keywords && row._keywords.length === 0" class="empty-hint">
                    词级明细待采集（采集器词层尚未覆盖该区间）
                  </div>
                </el-tab-pane>
                <el-tab-pane label="人群" name="crowd">
                  <el-table :data="row._crowds" size="small" max-height="420">
                    <el-table-column prop="crowdName" label="人群" min-width="200" show-overflow-tooltip />
                    <el-table-column prop="click" label="点击量" width="90" sortable />
                    <el-table-column prop="charge" label="花费" width="90" />
                    <el-table-column label="人群占比" width="110">
                      <template #default="{ row: c }">
                        <span :class="shareClass(c.crowdClickShare)">{{ fmtPct(c.crowdClickShare) }}</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </el-tab-pane>
              </el-tabs>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="unitName" label="单元" min-width="220" show-overflow-tooltip />
        <el-table-column prop="charge" label="花费" width="90" sortable />
        <el-table-column prop="click" label="点击量" width="95" sortable />
        <el-table-column prop="cpc" label="均价" width="90" sortable />
        <el-table-column prop="collectTotal" label="收藏" width="80" />
        <el-table-column prop="cartCount" label="加购" width="80" />
        <el-table-column prop="orderTotal" label="成交单数" width="95" sortable />
        <el-table-column prop="gmvTotal" label="成交金额" width="105" sortable />
        <el-table-column prop="roi" label="投产比" width="90" sortable />
        <el-table-column label="人群占比" width="120" sortable
                         :sort-method="(a, b) => (a.crowdClickShare ?? -1) - (b.crowdClickShare ?? -1)">
          <template #default="{ row }">
            <el-tooltip :content="crowdTip(row)" placement="top" :disabled="row.crowdClickShare == null">
              <span :class="shareClass(row.crowdClickShare)">{{ fmtPct(row.crowdClickShare) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="crowdClick" label="人群点击" width="95" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  GetPromoUnits,
  GetPromoUnitTrend,
  GetPromoUnitKeywords,
  GetPromoUnitCrowds,
} from '@/api/promoUnit'
import { GetPromoPlans } from '@/api/promoReport'

defineOptions({ name: 'promoUnit' })

// 计划 84290744044 是当前优化重点（10-17 reprice 对象），作为默认选中
const DEFAULT_CAMPAIGN = '84290744044'
// 人群占比低于该阈值（百分数）标红 —— 计划目的就是提升这个占比
const SHARE_WARN_BELOW = 80

const METRICS = [
  { key: 'click', label: '点击' },
  { key: 'charge', label: '花费' },
  { key: 'gmvTotal', label: '成交金额' },
  { key: 'roi', label: '投产比' },
  { key: 'collectTotal', label: '收藏' },
  { key: 'cartCount', label: '加购' },
  { key: 'crowdClickShare', label: '人群占比' },
]

const day = d => {
  const t = new Date(Date.now() - d * 86400000)
  return t.toISOString().slice(0, 10)
}
const futureDate = d => d > new Date()

const range = ref([day(14), day(1)])
const campaignId = ref(DEFAULT_CAMPAIGN)
const plans = ref([])
const units = ref([])
const loading = ref(false)
const expandedKeys = ref([])
const charts = {}
let booted = false

const fmtPct = v => (v == null ? '—' : `${Number(v).toFixed(2)}%`)
const shareClass = v => (v != null && v < SHARE_WARN_BELOW ? 'share-low' : 'share-ok')
const crowdTip = row =>
  `人群命中点击 ${row.crowdClick ?? 0} ÷ 单元总点击 ${row.click ?? 0}，` +
  `泛流量 ${Math.max((row.click ?? 0) - (row.crowdClick ?? 0), 0)} 次未落在任何人群上`
const fmtDate = s => (s ? s.slice(5) : '')

const loadPlans = async () => {
  const { data } = await GetPromoPlans()
  plans.value = data ?? []
  if (!plans.value.some(p => String(p.campaignId) === campaignId.value)) {
    campaignId.value = plans.value[0]?.campaignId ?? DEFAULT_CAMPAIGN
  }
}

const loadUnits = async () => {
  loading.value = true
  try {
    const { data } = await GetPromoUnits({
      campaignId: campaignId.value,
      from: range.value[0],
      to: range.value[1],
    })
    units.value = (data ?? []).map(u => ({
      ...u,
      _tab: 'trend',
      _metrics: ['click', 'charge'],
      _trend: null,
      _keywords: null,
      _crowds: null,
      _detailLoading: false,
    }))
  } finally {
    loading.value = false
  }
}

const reload = () => {
  chartsClear()
  expandedKeys.value = []
  loadUnits()
}

const setChartRef = (unitId, el) => {
  if (el) charts[unitId] = { el, chart: charts[unitId]?.chart ?? null }
}

const chartsClear = () => {
  Object.values(charts).forEach(c => c.chart?.dispose?.())
  Object.keys(charts).forEach(k => delete charts[k])
}

const loadDetail = async row => {
  if (row._trend) return
  row._detailLoading = true
  try {
    const q = { campaignId: campaignId.value, unitId: row.unitId,
                from: range.value[0], to: range.value[1] }
    const [t, k, c] = await Promise.all([
      GetPromoUnitTrend(q),
      GetPromoUnitKeywords({ ...q, sort: 'charge' }),
      GetPromoUnitCrowds(q),
    ])
    row._trend = t.data ?? []
    row._keywords = k.data ?? []
    row._crowds = c.data ?? []
    await nextTick()
    drawTrend(row)
  } finally {
    row._detailLoading = false
  }
}

const onExpand = (row, expandedList) => {
  expandedKeys.value = expandedList.map(r => r.unitId)
  if (expandedList.some(r => r.unitId === row.unitId)) loadDetail(row)
}

const drawTrend = row => {
  const c = charts[row.unitId]
  if (!c || !row._trend) return
  if (!c.chart) c.chart = echarts.init(c.el, 'dark')
  const picked = METRICS.filter(m => row._metrics.includes(m.key))
  const series = picked.map(m => ({
    name: m.label,
    type: 'line',
    smooth: true,
    connectNulls: true,
    data: row._trend.map(t => t[m.key] ?? null),
  }))
  c.chart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', valueFormatter: v => (v == null ? '—' : v) },
      legend: { top: 0 },
      grid: { left: 50, right: 20, top: 30, bottom: 25 },
      xAxis: { type: 'category', data: row._trend.map(t => fmtDate(t.statDate)) },
      yAxis: { type: 'value' },
      series,
    },
    true,
  )
}

onMounted(async () => {
  if (booted) return
  booted = true
  await loadPlans()
  await loadUnits()
})

onBeforeUnmount(chartsClear)
</script>

<style scoped>
.toolbar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  color: #909399;
  font-size: 12px;
}
.detail {
  padding: 4px 24px 12px 8px;
}
.trend-chart {
  height: 300px;
  width: 100%;
}
.metric-pick {
  margin-bottom: 4px;
}
.share-low {
  color: #f56c6c;
  font-weight: 600;
}
.share-ok {
  color: #67c23a;
}
.empty-hint {
  color: #909399;
  font-size: 13px;
  padding: 8px 0;
}
</style>
```

- [ ] **Step 2: 前端构建/语法验证**

```bash
# workdir: /Users/qyk9527/webstormProject/spzx-admin
npm run build 2>&1 | tail -5
```
Expected: 构建成功（vite 无报错）。若本机 dev 服务在跑，热更新后浏览器直接可见。

---

### Task 9: 一致性门 + 端到端验收

**Files:** 无新文件。

- [ ] **Step 1: 一致性门（新增 4 端点 vs 前端调用点）**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent
python3 scripts/check-consistency.py
```
Expected: 退出码 0。若 E 类报「前端调用点 vs 后端路由」漂移：核对 `promoUnit.js` 的 4 个 url 与 Controller 路径逐字一致（`/admin/promo/unit/units|trend|keywords|crowds`）。

- [ ] **Step 2: 起后端，页面端到端人工验收**

```bash
# workdir: /Users/qyk9527/ideaProject/spzx-parent
mvn spring-boot:run -pl spzx-manager
```
浏览器登录后台 → 运营 → 单元日报，验收清单：
1. 计划下拉默认 84290744044，单元列表有 67 行左右、各指标有值；
2. 人群占比列：有值的行按阈值着色；无人群数据的行显示「—」不出 0；
3. 点行展开 → 趋势图默认画点击+花费；勾「人群占比」「成交金额」等维度曲线跟随变化；
4. 关键词 tab：词行可见（Task 3 回补过 30 天），点列头能排序；
5. 人群 tab：人群行 + 占比列；抽一行人工核对：页面占比 ≈ SQL `(SELECT SUM(click) FROM promo_cost_item_daily WHERE dimension='crowd' AND unit_id='<该单元>' AND campaign_id='84290744044') / (同口径 dimension='item' 的 SUM(click))`；
6. 日期区间改到 2026-10-16 ~ 10-17，能看到 reprice 前后各维度变化（这是 owner 建页面的初始动机）；
7. 换一个没采词层的计划/区间：词表显示「词级明细待采集」，页面不报错。

- [ ] **Step 3: 收尾汇报**

向用户汇报：探针结论、词层行数、占比抽查结果、reprice 前后观察到的变化；提醒两仓库未提交（用户自己决定）。

---

## Self-Review 记录

- **Spec 覆盖**：spec §2 探针→Task 1；§3 数据模型→Task 2（entity_key 复合+单测）；§4 采集器→Task 2（--word-campaign-ids、crowd 默认值不动、台账并入 promo_cost_detail、词层失败不整批 failed——词块 break 后仍照常落单元行，与人群层同先例）；§5 后端→Task 5/6（四端点、先加总再除、分母0 NULL、无 join promo_plan 故无 COLLATE 坑）；§6 前端→Task 8（占比着色、tooltip 口径、维度勾选、词表降级占位）；§7 调度→Task 2 Step 7（cron 一行）；§8 验证→Task 2 单测 / Task 3 SQL 校验 / Task 6 单测 / Task 9 一致性+人工验收（含 reprice 前后对比）；§9 风险→Task 1 Step 3 失败分支、Task 3 Step 1 失败分支。
- **占位扫描**：词层 URL/sourceList/字段名客观未知——处理为 Task 1 产物 + Task 2 三处替换点（WORD_URL / word_body / word_of）+ 单测 fixture 同步说明，非 TBD。
- **类型一致性**：`word_of` 返回 `(str, str)`；`collect_words` 返回 `(rows, seen, pages)` 与 `collect_crowds` 同型；`args.word_page_size` 在 `collect_words` 与 main() 定义一致；XML 别名与 VO 字段逐一对过（unitId/unitName/days/crowdClick/crowdClickShare/statDate/keyword/bidwordId/crowdId/crowdName/unitClick）。
- **本仓库特例**：无 commit 步骤（Global Constraints 已声明，覆盖 skill 模板默认）。
