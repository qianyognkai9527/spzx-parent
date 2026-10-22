# 新标准计划选词+算出价（pick_plan_keywords）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建脚本 `automation/tb-auto/pick_plan_keywords.py`：给阿里妈妈关键词标准计划的每个商品单元重新选词，按手淘市场均价算基础出价，以广泛匹配写入新计划。

**Architecture:** 复用 `add_alimama_keywords.py`（单元枚举/抽屉候选/选词规则）与 `adjust_alimama_bid.py`（手淘均价/算价）的纯函数，新脚本只写编排 + 带 per-word `bidPrice` 的写入。默认 dry-run。

**Tech Stack:** Python 3.9（`automation/venv`）+ Playwright async + CDP 9222。测试用纯 `assert` 脚本（仓库惯例，见 `test_alimama_map.py`）。

## Global Constraints

- `automation/venv/bin/python`（3.9.6）；Chrome 必须在 **9222 窗口模式**且已登录万相台。禁止裸 `connect_over_cdp`，用 `sourcing/cdp_utils.connect_cdp`。
- 出价公式：`均价 / ((1+溢价%) × 折扣%)`，`money_floor2` 向下取到分，低于 min-bid 抬到 min-bid。
- 匹配方式全部广泛 = `matchScope=4`（页面默认）。
- **不改** `add_alimama_keywords.py` / `adjust_alimama_bid.py` 现有行为；只 `import` 其函数/常量。
- **不 commit**（项目规则：用户未要求绝不提交）。
- 默认 dry-run；报告 `pick_keywords_report.json` 是唯一断点状态（gitignore）。

---

### Task 1: 纯函数（双编码 URL + 报告 upsert）+ 单测

**Files:**
- Create: `automation/tb-auto/pick_plan_keywords.py`（先放纯函数骨架）
- Create: `automation/tb-auto/test_pick_plan_keywords.py`

**Interfaces:**
- Produces: `bq(word)->str`（双重 URL 编码）；`build_traffic_hash(word, cid="", aid="")->str`；`upsert(rep, aid, word, item)->None`

- [ ] **Step 1: 写失败测试** `automation/tb-auto/test_pick_plan_keywords.py`

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_plan_keywords import bq, build_traffic_hash, upsert

def test_bq_double_encodes():
    assert bq("女皮草") == "%25E5%25A5%25B3%25E7%259A%25AE%25E8%258D%2589"

def test_build_traffic_hash():
    h = build_traffic_hash("狐狸毛外套", "83949710619", "83872915734")
    assert h.startswith("#!/insight/search/traffic-analysis/index?word=")
    assert "campaignId=83949710619" in h and "adgroupId=83872915734" in h

def test_upsert_dedupes_by_unit_and_word():
    rep = {"items": []}
    upsert(rep, "1", "词a", {"adgroupId": "1", "word": "词a", "status": "dry"})
    upsert(rep, "1", "词a", {"adgroupId": "1", "word": "词a", "status": "ok"})
    assert len(rep["items"]) == 1 and rep["items"][0]["status"] == "ok"

if __name__ == "__main__":
    test_bq_double_encodes(); test_build_traffic_hash(); test_upsert_dedupes_by_unit_and_word()
    print("all ok")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `automation/venv/bin/python automation/tb-auto/test_pick_plan_keywords.py`
Expected: FAIL（`ModuleNotFoundError` / `ImportError`）

- [ ] **Step 3: 实现纯函数**

```python
from urllib.parse import quote

def bq(word):
    return quote(quote(word or "", safe=""), safe="")

def build_traffic_hash(word, cid="", aid=""):
    return (f"#!/insight/search/traffic-analysis/index?word={bq(word)}"
            f"&campaignId={cid}&adgroupId={aid}&bidwordId=")

def upsert(rep, aid, word, item):
    for i, old in enumerate(rep["items"]):
        if old.get("adgroupId") == aid and old.get("word") == word:
            rep["items"][i] = item
            return
    rep["items"].append(item)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `automation/venv/bin/python automation/tb-auto/test_pick_plan_keywords.py`
Expected: `all ok`

---

### Task 2: 网络捕获 + 带出价写入 + 报告 IO

**Files:**
- Modify: `automation/tb-auto/pick_plan_keywords.py`

**Interfaces:**
- Consumes: Task 1 的 `upsert`
- Produces: `load_report(path)`, `save_report(path, rep)`, `add_words_with_bid(page, cid, aid, items, tok, logf)->(ok,msg)`（`items` 每项 `{"word","bid","matchScope"}`）

- [ ] **Step 1: 实现**（沿用 `add_alimama_keywords.py` 的 `load_report/save_report` 写法与 `/bidword/add.json` fetch 写法，`bidPrice` 改为每词 `it["bid"]`、`matchScope` 取 `it["matchScope"]`）

```python
def load_report(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}

def save_report(path, rep):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)

async def add_words_with_bid(page, cid, aid, items, tok, logf):
    payload = {"bizCode": "onebpSearch", "csrfId": tok.get("csrfId"),
               "loginPointId": tok.get("loginPointId"), "bidwordList": []}
    for it in items:
        payload["bidwordList"].append({"campaignId": cid, "adgroupId": aid,
                                       "word": it["word"], "bidPrice": it["bid"],
                                       "matchScope": it["matchScope"], "recReason": None})
    res = await page.evaluate(r"""(p) => fetch('/bidword/add.json',
        {method:'POST', headers:{'content-type':'application/json'}, credentials:'include',
         body: JSON.stringify(p)}).then(r=>r.json()).then(j=>{
           const info=j.info||{};
           return {ok: info.ok!==false, err: info.message||info.errorMsg||null};
         }).catch(e=>({ok:false, err:String(e)}))""", payload)
    if not res.get("ok"):
        return False, str(res.get("err"))
    return True, "ok"
```

- [ ] **Step 2: 语法自检**

Run: `automation/venv/bin/python -c "import ast,sys; ast.parse(open('automation/tb-auto/pick_plan_keywords.py',encoding='utf-8').read())"`
Expected: 无输出（退出 0）

---

### Task 3: 单元编排（枚举→抽屉候选→选词→查均价→算价），dry-run 路径

**Files:**
- Modify: `automation/tb-auto/pick_plan_keywords.py`

**Interfaces:**
- Consumes: `add_alimama_keywords`（`get_units`/`goto_unit`/`open_drawer`/`click_tab`/`click_sub`/`existing_words`/`accepted_terms`/`pick_dim`/`dims_in`/`norm`/`COLLARS`/`LENGTHS`/`MATERIALS`/`_wait_type`/`_pick_with_fallback`）、`adjust_alimama_bid`（`market_avg`/`TRAFFIC`/`calc_bid`/`money_floor2`）、`connect_cdp`
- Produces: `async run(args)->int`（0/2/3/4）

- [ ] **Step 1: 实现网络嗅探（csrfId/loginPointId + kr/list.json 候选缓存）与 `run()`**

关键点（已实测）：
- 候选来源：`kr_fill_by_item`（AI选词，先切走再切回防缓存）、`kr_new_mta`（趋势机会词）。
- 均价：`market_avg(mkt_page, TRAFFIC.format(hash=build_traffic_hash(word)), args.source, logf)`。
- 先 `get_units` 拿单元（含暂停），`--adgroup-id`/`--limit-units` 过滤。
- 每单元：`goto_unit` → `existing_words` 去重 → `open_drawer` → 捕两来源 → 各自 `_pick_with_fallback` → 合并去重 → 逐词查均价 → `calc_bid`。
- 报告按 `(aid, word)` `upsert`；`status ∈ dry/ok/skip_no_market/fail`。
- 熔断：连续 8 次取不到均价 → 返回 4；`no_drawer`/`no_unit_page` 记 `skip_unit` 并继续。

- [ ] **Step 2: dry-run 冒烟（只读，用已知智能计划 83949710619，不改其数据）**

Run:
```
automation/venv/bin/python automation/tb-auto/pick_plan_keywords.py \
  --campaign-id 83949710619 --top 5 --limit-units 1 --gap 1 \
  --report /tmp/pick_kw_smoke.json --dry-run
```
Expected: 打印该单元入选词 + 手淘均价 + 算出价；无写入；退出 0。

- [ ] **Step 3: 核对 dry-run 与页面**

在新计划（或该单元）页面人工比对入选词是否落在标题品类、出价量级合理（如 均价0.50→0.35）。

---

### Task 4: apply 路径

**Files:**
- Modify: `automation/tb-auto/pick_plan_keywords.py`

- [ ] **Step 1: 加 `--apply` 分支**：有价词 `add_words_with_bid` 写入；写入失败且疑似风控（err 含 `2102001`/空）→ save 报告并返回 3 停本轮。
- [ ] **Step 2: 语法/单测自检**：`test_pick_plan_keywords.py` 通过；`python pick_plan_keywords.py --help` 有全部参数。
- [ ] **Step 3: apply 实跑**（**待用户建好新计划、给新 campaign-id 与溢价/折扣后**）：先用 `--limit-units 1` 试点 → 页面核对 → 全量 `--apply`。

---

### Task 5: 文档 + 留痕

**Files:**
- Modify: `automation/tb-auto/AGENTS.md`（加 `pick_plan_keywords.py` 一节：用途/公式/跑法/坑）
- Run: `automation/venv/bin/python scripts/log_work.py`（记「AI选词」模块）

---

## Self-Review

- **Spec coverage:** 选词(§2.2)=Task3；公式(§2.1)=Task3；匹配(§2.3)=Task2；复用不重写(§3)=Task1-3；CLI(§4)=Task3；边界(§6)=Task3 Step1；验证(§8)=Task3/4。✅
- **Placeholder scan:** 无 TODO/TBD。✅
- **Type consistency:** `build_traffic_hash`/`upsert`/`add_words_with_bid` 名称跨任务一致。✅
