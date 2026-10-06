# 淘宝穿戴甲 → 拼多多铺货 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Playwright + CDP 把人工指定的淘宝穿戴甲商品自动铺到拼多多「穿戴甲」类目商家后台，常态持续跑。

**Architecture:** 新建 `automation/pdd-auto/`。采集走淘宝千牛网页（复用现有淘宝登录/profile）；发布走独立 Chrome 9224 + 独立 profile。先 Phase 0 探路验证 PDD 后台可自动化，再落正式流水线；纯函数（价格/映射）TDD，浏览器步骤探路回填。

**Tech Stack:** Python 3.9（`automation/venv/bin/python`）、Playwright async、CDP、Chrome（`arch -arm64`，窗口模式）。

## Global Constraints

- 统一解释器：`/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python`（3.9）。
- 复用 `automation/sourcing/cdp_utils.py` 的 `connect_cdp(port, keep_urls, log)`；**禁裸 `connect_over_cdp`**；脚本结尾 `page.close()`。
- PDD 发布端口 **9224** + profile `automation/pdd-auto/chrome-profile`；采集走既有淘宝端口 **9222**。**不混端口**。
- Chrome 必须 `arch -arm64`；PDD 提交类用**窗口模式**（`--window-position=-32000,-32000`），勿 `--headless`/`--disable-gpu`。
- 价格：**淘宝价 ×1.3**（整店统一，SKU 价也乘）。
- 去重键：淘宝 `item_id`；`done` 跳过，`--retry-failed` 只放行 `failed`。
- 数据/登录态（`chrome-profile*`、`*.jsonl`、`*.json`、`pdd_notes/`）**不提交**（沿用 `.gitignore`）。
- 中文注释/日志，风格对齐 `sourcing/` 现有脚本。
- **本仓库规矩：未经用户明确要求不做 `git commit`**。本计划所有提交步骤暂缓，由用户决定时机。

## 文件结构

| 文件 | 职责 |
|---|---|
| `automation/pdd-auto/pdd_config.py` | 端口/路径/×1.3/类目常量（单一来源） |
| `automation/pdd-auto/run_chrome_pdd.sh` | 窗口模式起 9224 + profile |
| `automation/pdd-auto/probe_pdd_publish.py` | Phase 0：只读 dump PDD 发布页结构 |
| `automation/pdd-auto/pdd_map.py` | 纯函数：价格 ×1.3、标题清洗、SKU/属性映射 |
| `automation/pdd-auto/test_pdd_map.py` | 纯 assert 自检（仓库风格，无 pytest） |
| `automation/pdd-auto/collect_qianniu.py` | 千牛采集指定商品 → `taobao_product_data.jsonl` |
| `automation/pdd-auto/create_pdd_product.py` | PDD 发布，断点续跑 |
| `automation/pdd-auto/run_pdd_all.sh` | 冷却循环 wrapper |
| `automation/pdd-auto/pdd_notes/` | 探路产物（gitignore） |
| `automation/pdd-auto/AGENTS.md` | 本目录坑位（探路后回填） |

## 关键前提与已知风险

- **Phase 0 未过，不得写正式发布脚本**（PDD 反自动化强弱未知）。
- PDD 发布页字段/必填/图集要求：**由 Task 1 探路产出**，`create_pdd_product.py` 据此填写。
- 图源版权、PDD 发布配额：探路时观察（见 spec §10）。

---

### Task 1: 脚手架 + Phase 0 探路

**Files:**
- Create: `automation/pdd-auto/pdd_config.py`
- Create: `automation/pdd-auto/run_chrome_pdd.sh`
- Create: `automation/pdd-auto/probe_pdd_publish.py`
- Create: `automation/pdd-auto/AGENTS.md`
- Create: `automation/pdd-auto/pdd_notes/`（运行时生成）

**Interfaces:**
- Produces: `pdd_config` 常量（`CDP_PORT`, `PROFILE`, `PRICE_FACTOR`, `PDD_CATEGORY`, `MMS_GOODS_PUBLISH`, `TAOBAO_DATA`, `WORKLIST`, `PROGRESS`, `NOTES`, `SOURCING`）供后续所有任务 import。

- [ ] **Step 1: 写 `pdd_config.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 铺货配置: 端口/路径/系数集中一处."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SOURCING = os.path.abspath(os.path.join(BASE, "..", "sourcing"))

CDP_PORT = 9224
PROFILE = os.path.join(BASE, "chrome-profile")

PRICE_FACTOR = 1.3            # 淘宝价 × 1.3
PDD_CATEGORY = "穿戴甲"

MMS_HOME = "https://mms.pinduoduo.com/"
MMS_GOODS_PUBLISH = "https://mms.pinduoduo.com/goods/publish"

TAOBAO_DATA = os.path.join(BASE, "taobao_product_data.jsonl")
WORKLIST = os.path.join(BASE, "pdd_worklist.jsonl")
PROGRESS = os.path.join(BASE, "pdd_create_progress.json")
NOTES = os.path.join(BASE, "pdd_notes")
```

- [ ] **Step 2: 写 `run_chrome_pdd.sh`**

```bash
#!/usr/bin/env bash
# 启动 Chrome 9224 (PDD 铺货用) - 窗口模式(PDD 提交类不能用 headless), 离屏
arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9224 \
  --user-data-dir="/Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/chrome-profile" \
  --no-first-run \
  --disable-features=TranslateUI,site-per-process \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --window-position=-32000,-32000 --window-size=1400,900 \
  "https://mms.pinduoduo.com/"
```
然后 `chmod +x run_chrome_pdd.sh`。

- [ ] **Step 3: 写 `probe_pdd_publish.py`（只读 dump，不提交）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 发布页探路: 只读 dump 页面结构(字段/必填/控件), 不点提交.
跑法: automation/venv/bin/python probe_pdd_publish.py
前置: run_chrome_pdd.sh 已起 9224 且已登录 mms.pinduoduo.com
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402


async def main():
    b, ctx = await connect_cdp(C.CDP_PORT, keep_urls=["pinduoduo.com"], log=print)
    page = await ctx.new_page()
    try:
        await page.goto(C.MMS_GOODS_PUBLISH, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(6)
        url = page.url
        title = await page.title()
        body = (await page.inner_text("body"))[:4000]
        dom = await page.evaluate(
            """() => {
              const pick = (sel) => [...document.querySelectorAll(sel)].map(e => ({
                tag: e.tagName, id: e.id || '', name: e.name || '',
                text: (e.innerText || e.placeholder || e.getAttribute('aria-label') || '')
                        .replace(/\\s+/g, ' ').trim().slice(0, 60)
              })).filter(x => x.text);
              return {buttons: pick('button'), inputs: pick('input'),
                      selects: pick('select'), labels: pick('label'),
                      textareas: pick('textarea')};
            }"""
        )
        os.makedirs(C.NOTES, exist_ok=True)
        out = os.path.join(C.NOTES, f"probe_publish_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\nTITLE: {title}\n\n== BODY ==\n{body}\n\n== DOM ==\n{dom}\n")
        print("WROTE", out)
        print("URL:", url[:120])
        print("BODY(head):", body[:200].replace("\n", " "))
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
```

- [ ] **Step 4: 写 `AGENTS.md`（占位骨架，探路后回填）**

```markdown
# pdd-auto/ AGENTS.md

淘宝穿戴甲 → 拼多多铺货。CDP 9224（发布），采集走 9222（淘宝/千牛）。
Python 3.9，`automation/venv/bin/python`。

## 坑位（探路回填）
- （待填）PDD 发布页字段/必填/控件类型
- （待填）风控/验证码表现
```

- [ ] **Step 5: 起 Chrome 9224 并让用户扫码登录**

Run:
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto
nohup ./run_chrome_pdd.sh > /tmp/chrome9224_pdd.log 2>&1 &
open -na "Google Chrome"
```
Expected: `curl -s http://127.0.0.1:9224/json/version` 有返回；页面停在 PDD 登录页。
**人工动作**：请用户在离屏窗口扫码登录 PDD 商家后台（只此一次，登录态存入 profile）。

- [ ] **Step 6: 跑探路，确认发布页可达**

Run:
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto
/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python probe_pdd_publish.py
```
Expected: `pdd_notes/probe_publish_*.txt` 生成；`URL` 为 `mms.pinduoduo.com/goods/...` 而非登录页。
验证：文件里能看到类目/标题/价格等字段，或明确的风控/登录阻挡。

- [ ] **Step 7: 人工在发布页走一遍穿戴甲发布，记录坑位**

按 spec §5：dump 字段结构、必填、SKU/规格控件、图集/白底图要求、类目属性、提交入口、验证码。
把结论写进 `automation/pdd-auto/AGENTS.md`，并回填 spec §10。
**退出条件**：确认「CDP 能读字段 + 能脚本化提交一次」→ 继续 Task 4；否则转退路（第三方工具/开放平台 API），停止本计划。

---

### Task 2: 价格与映射纯函数（TDD）

**Files:**
- Create: `automation/pdd-auto/pdd_map.py`
- Create: `automation/pdd-auto/test_pdd_map.py`

**Interfaces:**
- Produces: `pdd_price(taobao_price) -> float|None`；`clean_pdd_title(title) -> str`。
- Consumes: `pdd_config.PRICE_FACTOR`。

- [ ] **Step 1: 写失败测试 `test_pdd_map.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdd_map 纯函数自检. 跑法: automation/venv/bin/python test_pdd_map.py"""
from pdd_map import pdd_price, clean_pdd_title

# 价格 ×1.3 四舍五入到 2 位
assert pdd_price(10) == 13.0
assert pdd_price(9.99) == 12.99          # 12.987 -> 12.99
assert pdd_price("19.9") == 25.87        # 25.87
assert pdd_price(0) is None
assert pdd_price(-3) is None
assert pdd_price(None) is None
assert pdd_price("abc") is None

# 标题清洗: 去首尾空白 + 折叠多空格
assert clean_pdd_title("  美甲  穿戴甲 ") == "美甲 穿戴甲"
assert clean_pdd_title("") == ""
print("OK: pdd_map 9 断言全过")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd automation/pdd-auto && ../../automation/venv/bin/python test_pdd_map.py`
Expected: FAIL `ModuleNotFoundError: No module named 'pdd_map'`

- [ ] **Step 3: 写最小实现 `pdd_map.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 铺货纯函数: 价格换算、标题清洗、字段映射."""
from pdd_config import PRICE_FACTOR


def pdd_price(taobao_price):
    """淘宝价 × PRICE_FACTOR, 四舍五入到 2 位. 非法/<=0 返回 None."""
    try:
        v = float(taobao_price)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return round(v * PRICE_FACTOR, 2)


def clean_pdd_title(title):
    """去首尾空白 + 折叠连续空白为一个空格."""
    return " ".join((title or "").split())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python test_pdd_map.py`
Expected: `OK: pdd_map 9 断言全过`

---

### Task 3: 千牛采集（`collect_qianniu.py`）

**Files:**
- Create: `automation/pdd-auto/collect_qianniu.py`

**Interfaces:**
- Consumes: `pdd_config`（`TAOBAO_DATA`）、`cdp_utils.connect_cdp`（端口 **9222**，`keep_urls=["myseller.taobao.com","item.upload.taobao.com"]`）。
- Produces: `taobao_product_data.jsonl`，字段见 spec §4。

- [ ] **Step 1: 探路千牛商品详情页字段**

用 9222 打开发布/编辑页 `https://item.upload.taobao.com/sell/v2/publish.htm?itemId=<id>`，dump 字段位置（标题、主图、详情图、SKU 价格/库存、货号）。
参考 `sourcing/AGENTS.md` 的 `sell-field-*` / `struct-*` 选择器与 `collect_in_stock_current.py`。
把有效选择器记入 `AGENTS.md`。

- [ ] **Step 2: 写采集脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""千牛采集: 指定淘宝 itemId -> 标题/主图/详情图/SKU/价格/库存 -> taobao_product_data.jsonl.
跑法: automation/venv/bin/python collect_qianniu.py --ids 123,456
前置: 9222 已登录淘宝/千牛.
注意: 选择器需按 Step1 探路结果填写(下方 EDIT 标记处).
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402

EDITOR = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}"
# EDIT(Step1 回填): 字段选择器
TITLE_SEL = "#sell-field-title input"      # 待探路核对
SKU_PRICE_SEL = "#sell-field-sku input"    # 待探路核对


async def collect_one(page, item_id):
    await page.goto(EDITOR.format(id=item_id), wait_until="domcontentloaded", timeout=40000)
    await asyncio.sleep(4)
    # EDIT(Step1 回填): 真实抽取逻辑
    return {"item_id": str(item_id), "title": "", "main_images": [], "detail_images": [],
            "skus": [], "price_min": None, "price_max": None, "code": None}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="逗号分隔的淘宝 itemId")
    args = ap.parse_args()
    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=print)
    page = await ctx.new_page()
    out = open(C.TAOBAO_DATA, "w", encoding="utf-8")
    try:
        for i in ids:
            rec = await collect_one(page, i)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print("collected", i, rec.get("title", "")[:30])
    finally:
        out.close()
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
```

- [ ] **Step 3: 验证**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python collect_qianniu.py --ids <真实id>`
Expected: `taobao_product_data.jsonl` 出现该商品、`title/skus/price_min` 非空。

---

### Task 4: PDD 发布脚本（`create_pdd_product.py`）— 依赖 Task 1 探路结论

**Files:**
- Create: `automation/pdd-auto/create_pdd_product.py`

**Interfaces:**
- Consumes: `pdd_config`（`CDP_PORT=9224`, `WORKLIST`, `PROGRESS`）、`cdp_utils.connect_cdp(9224, keep_urls=["pinduoduo.com"])`、`pdd_map`。
- Produces: `pdd_create_progress.json`（`done`/`failed`/`skipped`）。

- [ ] **Step 1: 读 Task 1 的 `pdd_notes/probe_publish_*.txt` + `AGENTS.md`，确定发布页选择器与流程**
- [ ] **Step 2: 写断点续跑骨架（与选择器无关的部分）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 发布: 按 pdd_worklist.jsonl 逐个在 mms 后台发布, 断点续跑.
跑法: automation/venv/bin/python create_pdd_product.py [--retry-failed] [--limit N] [--test]
进度: pdd_create_progress.json {done:[], failed:{}, skipped:[]}
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402


def load_prog():
    if os.path.exists(C.PROGRESS):
        try:
            return json.load(open(C.PROGRESS))
        except Exception:
            pass
    return {"done": [], "failed": {}, "skipped": []}


def save_prog(p):
    tmp = C.PROGRESS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
    os.replace(tmp, C.PROGRESS)


def load_worklist():
    rows = []
    with open(C.WORKLIST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


async def publish_one(page, item):
    """EDIT(Task1 回填): 打开发布页 -> 选类目 -> 填标题/属性/SKU/图 -> 提交. 返回 (ok, msg)."""
    return False, "未实现(待探路回填)"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    prog = load_prog()
    done = set(prog["done"])
    failed = set(prog["failed"])
    todo = []
    for x in load_worklist():
        iid = x["item_id"]
        if iid in done:
            continue
        if iid in failed and not args.retry_failed:
            continue
        todo.append(x)
    if args.limit:
        todo = todo[: args.limit]

    b, ctx = await connect_cdp(C.CDP_PORT, keep_urls=["pinduoduo.com"], log=print)
    page = await ctx.new_page()
    try:
        for n, item in enumerate(todo, 1):
            print(f"[{n}/{len(todo)}] item {item['item_id']}")
            ok, msg = await publish_one(page, item)
            if ok:
                prog["done"].append(item["item_id"])
                prog["failed"].pop(item["item_id"], None)
            else:
                prog["failed"][item["item_id"]] = msg
            save_prog(prog)
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
```

- [ ] **Step 3: 用 `--test` 单商品验证（不提交）**，确认能打开、选类目、填表。
- [ ] **Step 4: 单商品真实提交成功一次**，确认 `pdd_create_progress.json` 写入 `done`。

---

### Task 5: 冷却 wrapper + 收尾

**Files:**
- Create: `automation/pdd-auto/run_pdd_all.sh`

- [ ] **Step 1: 写 `run_pdd_all.sh`（仿 `sourcing/run_isv_republish.sh`）**

```bash
#!/usr/bin/env bash
# PDD 铺货 wrapper: 0=完成退出; 42=风控冷却(20m→40m→2h); 其他=5m 重试
cd "$(dirname "$0")"
LOG=pdd_run.log
COOLDOWN=1200
while true; do
  /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python create_pdd_product.py --retry-failed >> "$LOG" 2>&1
  code=$?
  echo "[$(date '+%m-%d %H:%M:%S')] create_pdd_product 退出码=$code" >> "$LOG"
  [ $code -eq 0 ] && { echo "[$(date '+%m-%d %H:%M:%S')] 完成, wrapper 退出" >> "$LOG"; break; }
  if [ $code -eq 42 ]; then
    sleep $COOLDOWN; COOLDOWN=$((COOLDOWN*2)); [ $COOLDOWN -gt 7200 ] && COOLDOWN=7200
  else
    sleep 300
  fi
done
```
`chmod +x run_pdd_all.sh`。

- [ ] **Step 2: 跑通 2-3 个商品端到端**，确认续跑（重跑跳过 `done`）。
- [ ] **Step 3: 回填 `AGENTS.md` 与 spec §10 未决项。**

---

## Self-Review

- **Spec 覆盖**：目录/端口（Task 1）、采集（Task 3）、价格×1.3（Task 2）、发布续跑去重（Task 4）、风控 wrapper（Task 5）、探路先行（Task 1）、测试（Task 2 纯 assert）—— 均有对应任务。
- **占位符**：Task 3/4 的浏览器选择器标注 `EDIT(探路回填)`，是**刻意的两阶段**（spec 明确 PDD 表单需探路产出），非遗忘型 TODO；其余步骤均有可运行代码。
- **类型一致**：`pdd_config` 常量名、`pdd_price/clean_pdd_title` 签名、progress 结构（`done`/`failed`/`skipped`）在 Task 2/4/5 间一致。
- **未覆盖**：落 DB/接多平台注册表 = spec 的 Phase 3（可选，本期非目标）。
