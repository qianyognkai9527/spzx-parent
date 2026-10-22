# ISV 商品管理映射全量重采 + 盈亏报表接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重采 ISV「商品管理」全量 (淘宝itemId ↔ 1688offerId) 映射并接入 `pnl_2026_report.py`，提高逐单采购成本配对覆盖率、落地刷单判定②。

**Architecture:** 修复 `scrape_isv_offer_taobao.py` 适配 ISV 后台 v3.5.51 改版（收起侧栏 + 飞出菜单导航），默认空关键词查全量 991 条，新增 `--offers` 按货源ID精查兜底；jsonl 与旧文件按 淘宝itemId 合并（防丢已删商品对）；`pnl_common.merge_offer_items()` 把 OSR 对与 jsonl 对合成 offer→[items]，报表配对循环改为遍历 item 列表。

**Tech Stack:** Python 3.9 (`automation/venv/bin/python`)、Playwright async + CDP 9222、MySQL `db_spzx`（dbconf）。

## Global Constraints

- **绝不 git commit**（用户红线：除非明确要求；本计划所有"验证"步骤只跑命令，无 commit 步骤）。
- 统一 `automation/venv/bin/python`（3.9，无 match、无 `X | Y` 类型语法）。
- 9222 Chrome 已在跑（headless，2026-10-14 实测 alive）；ISV 页面是纯浏览/查询，headless 安全（无提交类操作）。
- 勿与其它 1688 CDP 任务并行（账号级风控）。
- `isv_offer_taobao_map.jsonl` 必须**合并写**（新行覆盖同 taobao_item_id 旧行，旧行保留），不得直接覆盖丢历史对。
- MySQL 口令只走 `/tmp/spzx_my.cnf`（脚本内经 `pnl_common.connect_db`）。
- spec：`docs/superpowers/specs/2026-10-12-pnl-collector-design.md`（本计划对应其 §9）。

**背景数字（2026-10-14 探测实测）：**
- 旧 jsonl 994 对是关键词`甲`筛选产物 → 对 2026 在途+成功采购 offer 命中 **0/119**；现 OSR 映射(17 offers)命中 43/119。
- ISV 新 UI：侧栏 `首页/AI工具箱/货源中心/分销铺货/订单管理/我的/新手必读`；「商品管理」在 **分销铺货** flyout；侧栏收起态下 JS click 与 Playwright 常规 hover 均失效，须 `hover(force=True)` 于 `.ant-menu-submenu-title` + 真点击 flyout 项。
- 商品管理空关键词默认查询=全量 `共 991 条`（20/页）；按 `input#sourceProductIds` 货源ID精查可用（此模式行内 offer 提取可能为 None，以查询的 sid 为准）。
- 从未铺货的 offer（如手链 980520748851）无映射可采，照旧计未归属成本。

---

### Task 1: `merge_offer_items` 纯函数（TDD）

**Files:**
- Modify: `automation/tb-auto/pnl_common.py`（文件末尾追加）
- Test: `automation/tb-auto/test_pnl_isv_map.py`（新建，仿 `test_pnl_common.py` 的纯 assert 风格）

**Interfaces:**
- Produces: `merge_offer_items(osr_pairs, jsonl_pairs) -> tuple[dict[str, list[str]], list[tuple[str, str, str]]]`；入参为 `(offer, item)` 二元组可迭代；返回 (offer→去重item列表[OSR在前], 冲突列表[(offer, 首个osr_item, 新jsonl_item)])。Task 3 的报表调用。

- [ ] **Step 1: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_offer_items 单测: 纯 assert 风格, 直接运行。
跑法: automation/venv/bin/python automation/tb-auto/test_pnl_isv_map.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pnl_common import merge_offer_items

# 1) 并集去重, OSR 在前
m, c = merge_offer_items([("111", "A")], [("222", "B"), ("111", "A")])
assert m == {"111": ["A"], "222": ["B"]}, m
assert c == [], c

# 2) 同 offer 不同 item → 都保留, 记冲突
m, c = merge_offer_items([("111", "A")], [("111", "B")])
assert m["111"] == ["A", "B"], m
assert c == [("111", "A", "B")], c

# 3) 空值过滤
m, c = merge_offer_items([], [(None, "X"), ("", "Y"), ("333", "")])
assert m == {}, m
assert c == [], c

# 4) OSR 自身重复 offer 去重
m, c = merge_offer_items([("111", "A"), ("111", "A")], [])
assert m == {"111": ["A"]}, m

print("test_pnl_isv_map OK")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `automation/venv/bin/python automation/tb-auto/test_pnl_isv_map.py`
Expected: `ImportError: cannot import name 'merge_offer_items'`

- [ ] **Step 3: 最小实现**（追加到 `pnl_common.py` 末尾）

```python
def merge_offer_items(osr_pairs, jsonl_pairs):
    """offer → [item_id,...]: OSR(订单时点证据)在前, ISV商品管理(现绑定)去重并入。

    返回 (mapping, conflicts): conflicts=[(offer, 首个osr_item, 新jsonl_item)]。
    空 offer/item 一律丢弃; 同 offer 多 item 全部保留(配对循环逐个试)。
    """
    mapping = {}
    conflicts = []
    for off, it in osr_pairs:
        off, it = str(off) if off else "", str(it) if it else ""
        if not off or not it:
            continue
        lst = mapping.setdefault(off, [])
        if it not in lst:
            lst.append(it)
    for off, it in jsonl_pairs:
        off, it = str(off) if off else "", str(it) if it else ""
        if not off or not it:
            continue
        lst = mapping.setdefault(off, [])
        if it in lst:
            continue
        if lst:
            conflicts.append((off, lst[0], it))
        lst.append(it)
    return mapping, conflicts
```

- [ ] **Step 4: 跑测试确认通过**

Run: `automation/venv/bin/python automation/tb-auto/test_pnl_isv_map.py && automation/venv/bin/python automation/tb-auto/test_pnl_common.py`
Expected: 两个都输出 OK（后者回归确认没改坏旧函数）。

---

### Task 2: 抓取器适配新 UI + 全量重采

**Files:**
- Modify: `automation/sourcing/scrape_isv_offer_taobao.py`（docstring、导航、默认关键词、`--offers`、合并写）

**Interfaces:**
- Consumes: `cdp_utils.connect_cdp(9222, keep_urls=...)`。
- Produces: `automation/sourcing/isv_offer_taobao_map.jsonl`（每行 `{"taobao_item_id","offer_id","title"}`，合并写）。Task 3/4 消费。

- [ ] **Step 1: 改导航 + 查询 + `--offers` + 合并写**

要点（完整改动）：
1. docstring 更新：新 UI 路径（分销铺货→商品管理）、默认空关键词=全量、`--offers` 用法、合并写说明。
2. `--keyword` 默认改 `""`；新增 `--offers`（逗号分隔 1688 货源ID，逐个填 `input#sourceProductIds` 精查，行内 offer 为 None 时以 sid 为准）。
3. 导航函数：force hover `li.ant-menu-submenu`(has_text=分销铺货) 的 `.ant-menu-submenu-title` → 真点击 `.ant-menu-submenu-popup .ant-menu-item`(has_text=商品管理)；失败回退旧版 leaf-text JS click。
4. 查询函数：清三个输入框（fill timeout=2500 吞异常）→ 按需填 searchKey/sourceProductIds → JS 点 `button` 文本规范化后==`查询` → sleep 5。
5. 分页：`共 N 条`（去千分位逗号）→ 20/页；点页码 JS（`[class*=pagination] *` 文本==页码），失败点 `.ant-pagination-next`；每页读行后校验首页首行 taobao id 变化，不变则中止防死循环。
6. ROWS_JS 不变（新 UI 实测有效）。
7. 合并写：先读现有 jsonl 成 `{taobao_item_id: row}`，本run结果 update 进去，按 taobao_item_id 排序写回。

参考骨架（替换 `main()` 与新增 helpers；`ROWS_JS`/`get_frame`/`open_page` 保留）：

```python
async def nav_to_guanli(fr):
    try:
        await fr.locator("li.ant-menu-submenu", has_text="分销铺货").locator(".ant-menu-submenu-title").first.hover(force=True, timeout=6000)
        await asyncio.sleep(2)
        await fr.locator(".ant-menu-submenu-popup .ant-menu-item", has_text="商品管理").first.click(timeout=5000)
    except Exception as e:
        print(f"新UI导航失败({str(e)[:60]}), 回退旧版 leaf-text click")
        await fr.evaluate("""() => { const e=[...document.querySelectorAll('*')].find(x=>(x.children.length===0)&&(x.textContent||'').trim()==='商品管理'); if(e)e.click(); }""")
    await asyncio.sleep(6)


async def query(fr, search_key="", source_ids=""):
    for sel in ("input#shopProductIds", "input#sourceProductIds", "input#searchKey"):
        try:
            await fr.locator(sel).fill("", timeout=2500)
        except Exception:
            pass
    if search_key:
        await fr.locator("input#searchKey").fill(search_key, timeout=4000)
    if source_ids:
        await fr.locator("input#sourceProductIds").fill(source_ids, timeout=4000)
    await fr.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').replace(/\\s/g,'')==='查询'); if(b)b.click(); }""")
    await asyncio.sleep(5)


def read_total(fr_body_text):
    m = re.search(r"共\s*([\d,]+)\s*条", fr_body_text)
    return int(m.group(1).replace(",", "")) if m else 0


def load_existing(path):
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("taobao_item_id"):
                    out[str(r["taobao_item_id"])] = r
    return out
```

主循环（伪代码级要点，实现时保持与旧脚本相同的输出/进度打印风格）：
- `nav_to_guanli(fr)` 后：若 `args.offers` → 逐个 sid `query(fr, source_ids=sid)`，行 `{"taobao_item_id": r["taobao"], "offer_id": sid, "title": r["t"]}`（若 `r["offer"]` 且 ≠ sid，额外记 `{"taobao_item_id": r["taobao"], "offer_id": r["offer"], ...}`）；否则（全量/关键词）`query(fr, search_key=args.keyword)` → `read_total` → 逐页：点页码（JS 页码文本，异常则 `.ant-pagination-next`）→ sleep 3 → `ROWS_JS` 读行 → **首行 taobao id 与上一页相同则 break 并打印警告** → 收集。
- 结束：`merged = load_existing(OUT); merged.update({r["taobao_item_id"]: r for r in result})`；按 key 排序写回；打印 `WROTE ... 合并后 N 行(本次抓 M, 含offerId K)`。

- [ ] **Step 2: 单点验证（不碰 jsonl 之外的写）**

Run: `automation/venv/bin/python automation/sourcing/scrape_isv_offer_taobao.py --ids 1077395263073`
Expected: 打印 `命中 1 条, 1 页`、`1077395263073 -> 1055031942046`、`WROTE ... 合并后 994 行(本次抓 1, ...)`（行数以实际文件为准）。

- [ ] **Step 3: 全量重采（空关键词）**

Run: `automation/venv/bin/python automation/sourcing/scrape_isv_offer_taobao.py`
Expected: `命中 991 条, 50 页` 附近；结束打印合并后行数 ≥991；无分页卡死警告。

- [ ] **Step 4: 算出全量后仍缺的 top 采购 offer，`--offers` 补查**

```bash
cat > /tmp/top_missing_offers.py <<'EOF'
import json, sys, collections
sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto")
sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing")
from pnl_common import connect_db

pairs = set()
for line in open("/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/isv_offer_taobao_map.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("offer_id"):
        pairs.add(str(r["offer_id"]))
conn = connect_db(); cur = conn.cursor()
cur.execute("SELECT entries_json FROM purchase_order_1688 WHERE status_label IN ('交易成功','待发货','待收货')")
cnt = collections.Counter()
for (ej,) in cur.fetchall():
    for e in json.loads(ej or "[]"):
        if e.get("sourceId") and str(e["sourceId"]) not in pairs:
            cnt[str(e["sourceId"])] += 1
conn.close()
top = [o for o, _ in cnt.most_common(25)]
print(",".join(top))
EOF
automation/venv/bin/python /tmp/top_missing_offers.py
```

Run: `automation/venv/bin/python automation/sourcing/scrape_isv_offer_taobao.py --offers <上一步输出的逗号串>`
Expected: 每个 sid 打印命中行（命中 0 的打印空）；合并后行数上升。

- [ ] **Step 5: 覆盖复核**

Run: `automation/venv/bin/python /tmp/check_map_coverage.py`（Task 计划外已存在的探针，若被 /tmp 清理则按本计划 §背景数字里的代码重建）
Expected: 「offer可映射 N / 119」显著高于 43（手链类从未铺货的仍缺，属预期）。

---

### Task 3: 报表接入 jsonl 映射

**Files:**
- Modify: `automation/tb-auto/pnl_2026_report.py:49-57`（映射构建）与 `:117-129`（配对循环）、argparse、头部 docstring

**Interfaces:**
- Consumes: `pnl_common.merge_offer_items`（Task 1）、`../sourcing/isv_offer_taobao_map.jsonl`（Task 2）。
- Produces: 报告输出新增一行 `映射冲突` 日志；其余输出格式不变（Task 4 依赖）。

- [ ] **Step 1: 改 argparse + 映射构建**

```python
ap.add_argument("--isv-map", default=os.path.join(BASE, "..", "sourcing", "isv_offer_taobao_map.jsonl"),
                help="ISV商品管理 (淘宝itemId,1688offerId) 映射 jsonl")
```

映射构建（替换原 `cur.execute(...offer2item...)` 段）：

```python
osr_pairs = []
cur.execute("""
    SELECT DISTINCT s.source_product_id, i2.item_id
    FROM order_source_relation s
    JOIN order_info o2 ON o2.order_no=s.order_no AND o2.platform_type=1
    JOIN order_item i2 ON i2.order_id=o2.id
    WHERE s.platform_type=1 AND s.source_product_id IS NOT NULL AND s.source_product_id<>''
      AND i2.item_id IS NOT NULL AND i2.item_id<>''""")
osr_pairs = [(str(r[0]), r[1]) for r in cur.fetchall()]
jsonl_pairs = []
if os.path.exists(a.isv_map):
    with open(a.isv_map, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("offer_id") and r.get("taobao_item_id"):
                jsonl_pairs.append((str(r["offer_id"]), str(r["taobao_item_id"])))
offer2items, map_conflicts = merge_offer_items(osr_pairs, jsonl_pairs)
log(f"映射: OSR {len(osr_pairs)} 对 + ISV商品管理 {len(jsonl_pairs)} 对 → offer {len(offer2items)} 个"
    f" / 冲突(同offer多item,全保留) {len(map_conflicts)}")
```

（import 行把 `merge_offer_items` 加进 `from pnl_common import connect_db, log`。）

- [ ] **Step 2: 配对循环改遍历 item 列表**

```python
for p in live:
    cand = []
    seen_items = set()
    for off in p["offers"]:
        for it in offer2items.get(off, []):
            if it in seen_items:
                continue
            seen_items.add(it)
            for ono in item_orders.get(it, []):
                v = valid[ono]
                if v["matched"]:
                    continue
                lag = (p["time"] - v["create"]).total_seconds() / 86400.0
                if -1 <= lag <= a.purchase_window_days:
                    cand.append((abs(lag), ono))
    cand.sort()
    # ...以下不变
```

- [ ] **Step 3: docstring 口径更新 + 跑测试**

docstring 第 6 行改为：`1) offer→item_id 映射: order_source_relation×order_item(订单时点) ∪ ISV商品管理jsonl(现绑定,--isv-map);`
Run: `automation/venv/bin/python automation/tb-auto/test_pnl_isv_map.py`
Expected: OK。

---

### Task 4: 重跑报表 + 覆盖对比

**Files:**
- 产物: `/tmp/pnl_2026.csv`（覆盖）、`/tmp/pnl_full.csv`（新）

- [ ] **Step 1: 重跑 2026 报表**

Run: `automation/venv/bin/python automation/tb-auto/pnl_2026_report.py`
Expected: 日志含「映射: OSR … + ISV商品管理 … → offer N 个」；`配到单 M 张` 高于基线 41；总盈亏 ±0.01 内等于 **+¥40,100.52**（映射只影响归属，不动总额）。

- [ ] **Step 2: 重跑全窗口报表**

Run: `automation/venv/bin/python automation/tb-auto/pnl_2026_report.py --from 2024-10-01 --csv /tmp/pnl_full.csv`
Expected: 总盈亏 ±0.01 内等于 **+¥193,734.00**；`配到单` 高于基线 97；刷单嫌疑单数下降（记录新数）。

- [ ] **Step 3: 记录对比数字**（写进 Task 5 的 spec §9 与汇报）：映射对数 / offer数 / 配到采购张数(2026 & 全窗口) / 刷单嫌疑单数变化 / 冲突数。

---

### Task 5: 留痕

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-pnl-collector-design.md`（末尾追加 §9）
- 产物: `scripts/log_work.py` 台账行

- [ ] **Step 1: spec 追加 §9**（内容要点，数字用 Task 4 实测值）：
  - 2026-10-01 的 jsonl 是关键词`甲`筛选产物、非全量；不含"甲"的铺货商品（外套/派克服等）全漏 → 对 2026 采购 offer 命中 0/119。
  - ISV 后台 v3.5.51 改版坑：侧栏收起 + 菜单重组（商品管理→分销铺货 flyout、订单列表→订单管理 flyout）；收起态下 JS click 与常规 hover 均失效，须 `hover(force=True)` + 真点击；商品管理支持空关键词全量查询；按货源ID精查的行内 offer 可能为 None（以查询 sid 为准）。
  - 重采后映射 X 对；逐单配对 2026 M/119、全窗口 N/410；刷单嫌疑 K 单（旧 313）；冲突 C（同offer多item全保留）。
  - 从未铺货的 offer（如 980520748851 手链）无 ISV 映射——照旧计未归属成本，属数据边界非脚本 bug。
  - ISV 订单列表行级补采（原可选方案）未做，视覆盖数字再定。

- [ ] **Step 2: log_work 留痕**

```bash
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/log_work.py --module 其它 \
  --title "ISV商品管理映射全量重采+盈亏报表接入" --merge \
  --progress "映射X对; 2026配到M/119; 全窗口N/410; 刷单嫌疑K单"
```

---

## Self-Review

- 规格覆盖：设计 4 点（脚本适配/全量重采/--offers 兜底/报表接入+留痕）各有 Task；可选的订单列表补采明确不在本计划（Task 5 §9 记录待定）。
- 占位符：无 TBD/TODO；Task 4 数字待实测回填属预期（记进 §9）。
- 类型一致：`merge_offer_items(dict[str,list[str]])` 在 Task 1 定义、Task 3 以同名同形使用；jsonl 字段名 `taobao_item_id/offer_id` 全程一致。
