# ISV「规格匹配」全量过一遍（isv_sku_match）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `automation/sourcing/isv_sku_match.py`：把分销控制台「已关联货源」每个商品开「匹配规格」抽屉 → 点「自动匹配规格」→「确 认」；匹配不全/数量不等记录人工。

**Architecture:** 复用 `scrape_isv_offer_taobao.py` 的 iframe/菜单/翻页函数；新脚本写抽屉读写与编排。纯函数（规格名解析、计数/重复/未匹配判定、报告 upsert、CSV 行）可单测。默认 dry-run。

**Tech Stack:** Python 3.9（`automation/venv`）+ Playwright async + CDP 9222；测试=纯 assert 脚本（仓库惯例）。

## Global Constraints

- 只连 9222；`connect_cdp(9222, keep_urls=["fuwu_work_isv_container","isv-container","taobao.com","1688.com"])`。
- 抽屉可见性用 `.ant-drawer-open`（fixed 定位，offsetParent 恒 null，勿用）。
- 按钮/菜单一律 Playwright 真点击；侧栏菜单 `hover(force=True)`。
- 默认 `--dry-run`（读+记录+「取 消」关抽屉）；`--apply` 才点「自动匹配规格」+「确 认」。
- 异常终态（ok/manual_needed/count_mismatch/sku_duplicate/offer_delisted）只在 apply 阶段写入；dry-run 一律 `dry`。
- **不 commit**（项目规则）；报告/CSV 是数据文件（gitignore 域）。
- spec：`docs/superpowers/specs/2026-10-14-isv-sku-match-design.md`。

---

### Task 1: 纯函数 + 单测

**Files:**
- Create: `automation/sourcing/isv_sku_match.py`（先只放纯函数区）
- Create: `automation/sourcing/test_isv_sku_match.py`

**Interfaces:**
- Produces: `parse_spec_name(cell)->str`；`analyze_rows(rows, offer_specs)->dict`（rows=[{name,status,bound}]，offer_specs=[str] 或 None；返回 `{taobao_count, offer_count, unmatched:[...], duplicates:[...], count_mismatch:bool|None}`）；`upsert(rep, item_id, item)->None`；`manual_csv_rows(rep)->list[list]`

- [ ] **Step 1: 写失败测试** `automation/sourcing/test_isv_sku_match.py`

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isv_sku_match import parse_spec_name, analyze_rows, upsert, manual_csv_rows

def test_parse_spec_name():
    assert parse_spec_name("预览 2XL 灰色 价格：36.39元 库存：10000") == "2XL 灰色"
    assert parse_spec_name("价格：36.39元") == ""          # 无规格名
    assert parse_spec_name("预览 M 价格：1元 库存：2") == "M"

def test_analyze_rows_count_mismatch_and_unmatched():
    rows = [{"name": "M", "status": "已匹配", "bound": "灰色-M"},
            {"name": "L", "status": "未匹配", "bound": ""}]
    a = analyze_rows(rows, ["灰色-M", "灰色-L", "灰色-XL"])
    assert a["taobao_count"] == 2 and a["offer_count"] == 3
    assert a["count_mismatch"] is True
    assert a["unmatched"] == ["L"]

def test_analyze_rows_duplicate_binding():
    rows = [{"name": "M", "status": "已匹配", "bound": "灰色-M"},
            {"name": "L", "status": "已匹配", "bound": "灰色-M"}]
    a = analyze_rows(rows, ["灰色-M"])
    assert a["duplicates"] == ["灰色-M"]
    assert a["count_mismatch"] is False

def test_analyze_rows_no_offer_specs():
    a = analyze_rows([{"name": "M", "status": "已匹配", "bound": "灰色-M"}], None)
    assert a["count_mismatch"] is None and a["offer_count"] is None

def test_upsert_and_csv():
    rep = {"items": []}
    upsert(rep, "1", {"item_id": "1", "status": "dry"})
    upsert(rep, "1", {"item_id": "1", "status": "manual_needed", "unmatched": ["L"]})
    upsert(rep, "2", {"item_id": "2", "status": "count_mismatch", "title": "T"})
    assert len(rep["items"]) == 2 and rep["items"][0]["status"] == "manual_needed"
    rows = manual_csv_rows(rep)
    # manual_needed 一行一规格；count_mismatch 一行
    assert ["1", "L", "manual_needed"] == rows[0][:3]
    assert rows[1][2] == "count_mismatch"

if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"): v()
    print("all ok")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `automation/venv/bin/python automation/sourcing/test_isv_sku_match.py`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现纯函数**

```python
import re

def parse_spec_name(cell):
    """'预览 2XL 灰色 价格：36.39元 库存：10000' -> '2XL 灰色'。"""
    m = re.search(r"预览\s+(.*?)\s*价格：", cell or "")
    return m.group(1).strip() if m else ""

def analyze_rows(rows, offer_specs):
    """rows=[{name,status,bound}]；offer_specs=1688规格名清单或 None。
    返回 {taobao_count, offer_count, unmatched, duplicates, count_mismatch}。"""
    names = [r["name"] for r in rows if r.get("name")]
    unmatched = [r["name"] for r in rows
                 if r.get("name") and (r.get("status") or "").strip() != "已匹配"]
    dup = []
    seen = {}
    for r in rows:
        b = (r.get("bound") or "").strip()
        if b:
            seen[b] = seen.get(b, 0) + 1
    dup = sorted(k for k, v in seen.items() if v > 1)
    if offer_specs is None:
        return {"taobao_count": len(names), "offer_count": None,
                "unmatched": unmatched, "duplicates": dup, "count_mismatch": None}
    return {"taobao_count": len(names), "offer_count": len(offer_specs),
            "unmatched": unmatched, "duplicates": dup,
            "count_mismatch": len(names) != len(offer_specs)}

FINAL = {"ok", "manual_needed", "count_mismatch", "sku_duplicate", "offer_delisted"}

def upsert(rep, item_id, item):
    for i, old in enumerate(rep["items"]):
        if old.get("item_id") == item_id:
            rep["items"][i] = item
            return
    rep["items"].append(item)

def manual_csv_rows(rep):
    """人工处理清单：manual_needed 每个未匹配规格一行；count_mismatch/sku_duplicate 各一行。"""
    out = []
    for it in rep["items"]:
        st = it.get("status")
        if st == "manual_needed":
            for name in it.get("unmatched", []):
                out.append([it.get("item_id", ""), it.get("title", ""), "manual_needed", name])
        elif st in ("count_mismatch", "sku_duplicate"):
            out.append([it.get("item_id", ""), it.get("title", ""), st,
                        json.dumps({k: v for k, v in it.items()
                                    if k in ("taobao_sku_count", "offer_spec_count",
                                             "duplicates", "unmatched")}, ensure_ascii=False)])
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `automation/venv/bin/python automation/sourcing/test_isv_sku_match.py`
Expected: `all ok`

---

### Task 2: 抽屉读写 JS + 页面辅助（复用 scrape_isv_offer_taobao）

**Files:**
- Modify: `automation/sourcing/isv_sku_match.py`

**Interfaces:**
- Consumes: `scrape_isv_offer_taobao.get_frame / nav_to_guanli / select_tab / click_next`（已存在，直接 import）
- Produces: `async read_drawer_rows(fr)->list`；`async read_offer_specs(fr)->list|None`；`async click_btn(fr, label)->bool`（抽屉内按钮）；`async open_match_drawer(fr, row_idx)->bool`；`async close_drawer(fr, save=False)->str`

- [ ] **Step 1: 实现**（要点，选择器均为探针实测）：
  - `read_drawer_rows`：`.ant-drawer-open` 内 `tbody tr` → cell0=parse_spec_name(innerText)、cell1=规格状态、cell3 下拉当前值（`.ant-select-selection-item,.next-select-selection-item`）。
  - `read_offer_specs`：点首行下拉展开 → 读 `.ant-select-dropdown:not(.ant-dropdown-hidden) .ant-select-item-option,.ant-select-item` 文本 → Escape 收起；取不到返回 None（计数校验记 None 不判 mismatch）。
  - `click_btn(fr,label)`：`.ant-drawer-open` 内 `button`，innerText 去空格 == label（`确认`/`取消`/`自动匹配规格`）。
  - `open_match_drawer(fr,row_idx)`：该行「更多」→ 下拉项「匹配规格」→ 等 `.ant-drawer-open`（轮询 10s）。
  - `close_drawer(fr,save)`：save=False 点「取消」，True 点「确认」；返回按钮是否点到。
- [ ] **Step 2: 语法自检**

Run: `automation/venv/bin/python -c "import ast; ast.parse(open('automation/sourcing/isv_sku_match.py',encoding='utf-8').read())"`
Expected: 退出 0

---

### Task 3: 编排 run()（翻页全量 + 逐行抽屉 + dry-run/apply + 续跑）

**Files:**
- Modify: `automation/sourcing/isv_sku_match.py`

**Interfaces:**
- Consumes: Task1 纯函数、Task2 抽屉函数、`scrape_isv_offer_taobao` 导航件、`load_report/save_report`（同 add_alimama_keywords 写法）
- Produces: `async run(args)->int`（0 正常 / 3 风控或连续抽屉失败熔断）

- [ ] **Step 1: 实现**：
  - 导航：get_frame → 「重 置」清筛选残留 → select_tab("已关联货源") → 读总行数分页。
  - 逐行：`item_id`=行文本 `ID：(\d+)`（货源 offerId=货源信息列 `ID：(\d+)`）；报告已有终态（FINAL）且非 --force → 跳过；开抽屉 → 读行+读 offer_specs → analyze →
    - dry-run：status=`dry`（anomalies 放字段）→ 取消关抽屉；
    - apply：点「自动匹配规格」→ 等 2s 轮询回读行状态 → analyze → 点「确 认」→ status=ok/manual_needed/count_mismatch/sku_duplicate（按 analyze）→ 保存报告。
  - 抽屉打不开 → `drawer_fail`，连续 5 个 → 熔断 exit 3。
  - 翻页：click_next 直到无下一页；每行 `--gap`（默认 10）。
  - `--limit N`（试点）、`--force`、`--report`、`--csv`。
- [ ] **Step 2: dry-run 冒烟（只读，抽屉开了就取消，不保存）**

Run:
```
automation/venv/bin/python automation/sourcing/isv_sku_match.py --limit 2 --dry-run \
  --report /tmp/sku_match_smoke.json
```
Expected: 2 行记录 `dry` + 行数/绑定/异常明细；无「自动匹配规格」「确 认」点击；退出 0。

- [ ] **Step 3: 抽查核对**：人工开控制台比对同一商品的规格绑定与报告一致。

---

### Task 4: apply 首轮试点 + 全量

**Files:**
- Modify: `automation/sourcing/isv_sku_match.py`（如试点暴露行为差异则修）

- [ ] **Step 1: `--limit 1 --apply` 试点（用户盯着看）**：确认「自动匹配规格」不乱重绑已匹配行、确认保存生效（列表行状态、抽屉重开核对）。
- [ ] **Step 2: 试点通过后全量**：`nohup venv/bin/python -u automation/sourcing/isv_sku_match.py --apply --gap 10 > /tmp/sku_match_run.log 2>&1 &`（≈29h，分多晚断点续跑）。
- [ ] **Step 3: 收尾**：报告汇总 + `sku_match_manual.csv` 交人工。

---

### Task 5: 文档 + 留痕

- [ ] `automation/sourcing/AGENTS.md` 加 `isv_sku_match.py` 一节（用途/跑法/坑：drawer-open 判可见、首轮试点、时长）。
- [ ] `automation/venv/bin/python scripts/log_work.py --module "淘宝SKU" --title "ISV规格匹配全量脚本" …`

---

## Self-Review

- **Spec coverage:** 流程§3=Task3；抽屉结构§2=Task2；报告/续跑§4=Task1+3；长跑§6=Task4；坑§7=Global Constraints；未决§8=Task4 Step1 试点验证。✅
- **Placeholder scan:** 无 TBD/TODO；JS 块以选择器+行为描述（选择器即实现内容）。✅
- **Type consistency:** `analyze_rows`/`upsert`/`manual_csv_rows`/`FINAL` 跨任务一致。✅
