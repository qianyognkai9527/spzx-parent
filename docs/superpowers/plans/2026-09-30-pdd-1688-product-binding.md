# PDD商品↔1688货源关联维护 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已铺到拼多多的商品导入后台 `platform_product`(type=3)，并建立到 1688 货源的**商品级**关联，后台可查看/维护。

**Architecture:** 采集侧（automation）产出两份映射：ISV 铺货日志 `(1688 offerId↔淘宝 itemId)`、pdd-auto 发布记录 `(PDD goods_id↔淘宝 itemId)`；join 后按 1688 offerId 命中 `source_product`，导入 `platform_product(3)` + `product_bind_relation`。后台复用现有 `mallProduct.vue` + `ProductBindRelation` 接口（平台无关），仅需启用注册表 `platform.code=3` 与 `shop.id=3`。

**Tech Stack:** Python 3.9（`automation/venv/bin/python`）+ Playwright/CDP；pymysql；Spring Boot/MyBatis-Plus（几乎不改）；Vue3（不改代码，靠注册表）。

## Global Constraints

- 统一解释器：`/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python`（3.9）。
- CDP 复用 `sourcing/cdp_utils.connect_cdp`；采集走 9222（淘宝/1688）；PDD 发布 9224。
- 关联**只做商品级**（`product_bind_relation`），不做 SKU 级。
- 幂等键：PDD `goods_id`（写入 `platform_product.code`，唯一）。
- 不新建表；不改 `ProductBindRelationServiceImpl`（平台无关）。
- 数据/登录态/进度文件不提交（沿用 `.gitignore`）。
- **本仓库规矩：未经用户明确要求不 `git commit`**；计划中的提交步骤一律暂缓。
- MySQL：`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx`。

## 文件结构

| 文件 | 职责 |
|---|---|
| `automation/sourcing/scrape_isv_offer_taobao.py` | 读 ISV 铺货成功/全部列表 → `(offerId, 淘宝itemId)` → `isv_offer_taobao_map.jsonl` |
| `automation/pdd-auto/create_pdd_product.py`（改） | 提交成功时把 `goods_id/item_id/title/price/images` 追加到 `pdd_products.jsonl` |
| `automation/pdd-auto/build_pdd_bind_worklist.py` | 纯函数 join：pdd 记录 × ISV 映射 × source_product → 待写关联 |
| `automation/pdd-auto/test_pdd_bind_worklist.py` | join 纯函数自检（assert） |
| `automation/pdd-auto/import_pdd_products.py` | upsert `platform_product(3)` + `product_bind_relation` |
| （数据）`sql/` 或 mysql | 启用 `platform`(code=3) 与 `shop`(id=3) |

## 关键事实（实现依据）

- `source_product.source_product_code` = 1688 货源 ID（varchar(50)，有索引）。
- `platform_product`：`code` 唯一，`platform_type`，`title`，`pricing`，`shop_id`，`create_by/create_time/update_by/update_time/remark`。
- `product_bind_relation`：`product_id`(=platform_product.id) ↔ `source_productId`(=source_product.id)，`is_deleted`。
- 注册表：`platform` code=3 `pinduoduo` 当前 `enabled=0`；`shop` id=3 `拼多多默认店` `platform_code=3` `status=0`。
- 后端 `findUnBindSourceProduct(ProductBindQueryDto)` 按 `sourceProductName` 模糊查 `source_product`，**不分平台**；`bindRelation` 只写 `product_id/source_productId`。

---

### Task 1: Phase 0 spike —— ISV 铺货日志能拿到淘宝 itemId

**Files:**
- Create: `automation/sourcing/scrape_isv_offer_taobao.py`

**Interfaces:**
- Produces: `isv_offer_taobao_map.jsonl`，每行 `{"offer_id": str, "taobao_item_id": str|null, "title": str}`。

- [ ] **Step 1: 探路 ISV 铺货列表页**

前置：9222 已登录 1688，且**人工点开「铺货日志 → 铺货成功/全部」tab**（Ant SPA 菜单脚本点不动，见 `sourcing/AGENTS.md`）。
Run（只读 dump）：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python - <<'PY'
import asyncio, sys
sys.path.insert(0, '.')
from cdp_utils import connect_cdp
async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container","isv-container","1688.com"], log=print)
    page = ctx.pages[0]
    txt = await page.inner_text("body")
    print(txt[:1500])
    b.close()
asyncio.run(main())
PY
```
Expected: 打印列表行文本，确认每行是否出现**淘宝商品ID/itemId**（或只有 offerId）。把有效选择器记入 `sourcing/AGENTS.md`。
**若列表不含 itemId**：改从行「详情」打开获取，或明确标注该项不可得 → 上报用户，改用「淘宝 itemId 缺失则关联留空」的降级路径（见 Task 3 Step 3）。

- [ ] **Step 2: 写采集脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISV 铺货日志采集: (1688 offerId, 淘宝 itemId) -> isv_offer_taobao_map.jsonl.
前置: 9222 已登录 1688 且人工点开「铺货日志 -> 铺货成功/全部」tab.
选择器按 Step1 探路结果填写(下方 EDIT).
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_utils import connect_cdp  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isv_offer_taobao_map.jsonl")


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container", "isv-container", "1688.com"], log=print)
    page = ctx.pages[0]
    # EDIT(Step1 回填): 逐行取 offerId / itemId / title
    rows = await page.evaluate("""() => {
      const out = [];
      for (const tr of document.querySelectorAll('tr')) {
        const t = (tr.innerText || '').replace(/\\s+/g, ' ').trim();
        if (!t) continue;
        const offer = (t.match(/(\\d{9,})/g) || [])[0] || null;
        const item = (t.match(/itemId[=: ]?(\\d{9,})/i) || [])[1] || null;
        out.push({offer_id: offer, taobao_item_id: item, title: t.slice(0, 60)});
      }
      return out;
    }""")
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("WROTE", OUT, len(rows))
    await b.close()


asyncio.run(main())
```

- [ ] **Step 3: 验证**

Run: `/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python scrape_isv_offer_taobao.py`
Expected: `isv_offer_taobao_map.jsonl` 生成；抽查行含 offer_id 与 taobao_item_id。

---

### Task 2: pdd-auto 记录发布结果 + 回填 4 条

**Files:**
- Modify: `automation/pdd-auto/create_pdd_product.py`
- Modify: `automation/pdd-auto/pdd_config.py`（新增 `PDD_PRODUCTS` 路径）

**Interfaces:**
- Produces: `pdd_products.jsonl`，每行 `{"pdd_goods_id": str, "item_id": str, "title": str, "price": float, "images": [str]}`。
- Consumes: 成功页 URL `.../goods_add/success?goods_id=xxx&...`。

- [ ] **Step 1: 加路径常量**

`pdd_config.py` 增加：
```python
PDD_PRODUCTS = os.path.join(BASE, "pdd_products.jsonl")
```

- [ ] **Step 2: 成功时写记录**

在 `create_pdd_product.py` 顶加：
```python
import re


def record_pdd_product(page_url, rec):
    m = re.search(r"goods_id=(\d+)", page_url)
    if not m:
        return
    row = {"pdd_goods_id": m.group(1), "item_id": rec["item_id"],
           "title": rec["title"], "price": rec["price"], "images": rec["images"]}
    with open(C.PDD_PRODUCTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
```
在 `publish_one` 的成功分支里、`return True` 之前调用：
```python
        if "success" in page.url or "goods_list" in page.url:
            record_pdd_product(page.url, rec)
            return True, "已上架(跳转成功页) | " + fmsg
```

- [ ] **Step 3: 回填已上架 4 条**

从已存在的成功页 URL 取 goods_id（`) 与 `pdd_worklist.jsonl` 的 item_id 配对，手动生成 4 行追加到 `pdd_products.jsonl`（或重跑会覆盖；本次手工回填）：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto
grep -h "goods_add/success" pdd_notes/submit_result_*.txt | sed -E 's/.*goods_id=([0-9]+).*/\1/'
```
Expected: 列出 4 个 goods_id；与 `pdd_worklist.jsonl` 合成 `pdd_products.jsonl`。

- [ ] **Step 4: 验证**

Run: `/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python -c "import json;print(sum(1 for _ in open('pdd_products.jsonl')))"`
Expected: `4`。

---

### Task 3: join + 导入（TDD 纯函数 + 写库）

**Files:**
- Create: `automation/pdd-auto/build_pdd_bind_worklist.py`
- Create: `automation/pdd-auto/test_pdd_bind_worklist.py`
- Create: `automation/pdd-auto/import_pdd_products.py`

**Interfaces:**
- `build_pdd_bind_worklist.build(products, isv_map, source_by_code) -> list[dict]`
  - 入参：`products`=[{pdd_goods_id,item_id,title,price}], `isv_map`={item_id: offer_id}, `source_by_code`={offer_id: source_product_id}
  - 出参：每项 `{"pdd_goods_id","item_id","title","price","offer_id"|None,"source_product_id"|None}`
- `import_pdd_products.import_rows(rows, conn)` → upsert `platform_product(3)` + `product_bind_relation`。

- [ ] **Step 1: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_pdd_bind_worklist 纯函数自检. 跑法: automation/venv/bin/python test_pdd_bind_worklist.py"""
from build_pdd_bind_worklist import build

products = [
    {"pdd_goods_id": "g1", "item_id": "t1", "title": "A", "price": 10.0},
    {"pdd_goods_id": "g2", "item_id": "t2", "title": "B", "price": 20.0},
    {"pdd_goods_id": "g3", "item_id": "t3", "title": "C", "price": 30.0},
]
isv_map = {"t1": "o1", "t2": "o2"}                 # t3 不在 ISV 记录
source_by_code = {"o1": 101}                        # o2 的 offer 未收录进 source_product
out = build(products, isv_map, source_by_code)
assert out[0]["offer_id"] == "o1" and out[0]["source_product_id"] == 101
assert out[1]["offer_id"] == "o2" and out[1]["source_product_id"] is None   # offer 未收录
assert out[2]["offer_id"] is None and out[2]["source_product_id"] is None   # item 无 ISV 记录
assert [r["pdd_goods_id"] for r in out] == ["g1", "g2", "g3"]
print("OK: build_pdd_bind_worklist 3 断言全过")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python test_pdd_bind_worklist.py`
Expected: FAIL `ModuleNotFoundError: build_pdd_bind_worklist`

- [ ] **Step 3: 写最小实现**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""join pdd 发布记录 × ISV 映射 × source_product -> 待导入关联(纯函数)."""
import json
import os

import pdd_config as C


def build(products, isv_map, source_by_code):
    out = []
    for p in products:
        offer = isv_map.get(str(p["item_id"]))
        src = source_by_code.get(str(offer)) if offer else None
        out.append({
            "pdd_goods_id": str(p["pdd_goods_id"]),
            "item_id": str(p["item_id"]),
            "title": p.get("title", ""),
            "price": p.get("price"),
            "offer_id": offer,
            "source_product_id": src,
        })
    return out


def _load_jsonl(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_all():
    products = _load_jsonl(C.PDD_PRODUCTS)
    isv = {str(r["taobao_item_id"]): str(r["offer_id"]) for r in _load_jsonl(
        os.path.join(C.SOURCING, "isv_offer_taobao_map.jsonl")) if r.get("taobao_item_id")}
    return products, isv


if __name__ == "__main__":
    products, isv = load_all()
    print("products", len(products), "isv", len(isv))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python test_pdd_bind_worklist.py`
Expected: `OK: build_pdd_bind_worklist 3 断言全过`

- [ ] **Step 5: 写 `import_pdd_products.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入 PDD 商品到 platform_product(3) 并建立到 1688 货源的商品级关联(幂等).
跑法: automation/venv/bin/python import_pdd_products.py [--dry-run]
"""
import argparse
import sys

import pymysql

import pdd_config as C
from build_pdd_bind_worklist import build, load_all

DB = dict(host="127.0.0.1", user="root", password="root123456", database="db_spzx", port=3306, charset="utf8mb4")
PDD_PLATFORM = 3
PDD_SHOP_ID = 3


def source_by_code(conn):
    out = {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, source_product_code FROM source_product WHERE is_deleted=0")
        for pid, code in cur.fetchall():
            if code:
                out[str(code)] = pid
    return out


def upsert_platform_product(conn, r):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM platform_product WHERE code=%s", (r["pdd_goods_id"],))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE platform_product SET title=%s, pricing=%s, platform_type=%s, shop_id=%s WHERE id=%s",
                        (r["title"], r["price"], PDD_PLATFORM, PDD_SHOP_ID, row[0]))
            return row[0]
        cur.execute("INSERT INTO platform_product(code,title,platform_type,shop_id,pricing,create_by,create_time) "
                    "VALUES(%s,%s,%s,%s,%s,0,NOW())",
                    (r["pdd_goods_id"], r["title"], PDD_PLATFORM, PDD_SHOP_ID, r["price"]))
        return cur.lastrowid


def bind(conn, product_id, source_product_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product_bind_relation WHERE product_id=%s AND source_productId=%s AND is_deleted=0",
                    (product_id, source_product_id))
        if cur.fetchone():
            return
        cur.execute("INSERT INTO product_bind_relation(product_id,source_productId,create_by,create_time,is_deleted) "
                    "VALUES(%s,%s,0,NOW(),0)", (product_id, source_product_id))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    products, isv = load_all()
    conn = pymysql.connect(**DB)
    try:
        sbc = source_by_code(conn)
        rows = build(products, isv, sbc)
        missing = [r for r in rows if not r["source_product_id"]]
        for r in rows:
            pid = upsert_platform_product(conn, r) if not args.dry_run else -1
            if r["source_product_id"]:
                if not args.dry_run:
                    bind(conn, pid, r["source_product_id"])
                print(f"绑定 {r['pdd_goods_id']} -> source {r['source_product_id']}")
            else:
                print(f"⚠ 未关联 {r['pdd_goods_id']} (item={r['item_id']} offer={r['offer_id']})")
        if not args.dry_run:
            conn.commit()
        print(f"共 {len(rows)}，未关联 {len(missing)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: dry-run 验证**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python import_pdd_products.py --dry-run`
Expected: 打印 4 行「绑定/未关联」；未关联项列出缺失 offer 或 item。

---

### Task 4: 启用 PDD 平台/店铺 + 后台验证

**Files:**
- Modify（数据）: `platform` 表 code=3；`shop` 表 id=3

- [ ] **Step 1: 启用注册表与店铺**

Run:
```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "UPDATE platform SET enabled=1 WHERE code=3; UPDATE shop SET status=1 WHERE id=3 AND platform_code=3;"
```
注意：`shop` 还要求 `is_default` 与 `status` 不能是「is_default=1 + status=0」的非法组合（09-29 spec §D 记录过 id=3 原本就是该非法组合）——启用前先确认组合合法。

- [ ] **Step 2: 真实导入**

Run: `cd automation/pdd-auto && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python import_pdd_products.py`
Expected: 4 条 platform_product(3) + bind 写入。

- [ ] **Step 3: DB 复核**

Run:
```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SELECT id,code,title,platform_type,shop_id,pricing FROM platform_product WHERE platform_type=3; SELECT product_id,source_productId FROM product_bind_relation WHERE product_id IN (SELECT id FROM platform_product WHERE platform_type=3);"
```
Expected: 4 行 PDD 商品，且各有 1 条 bind。

- [ ] **Step 4: 后台验证**

打开 `spzx-admin`（3001）商品页，切到「拼多多」tab → 看到 4 个商品；点「已关联货源商品」看到 1688 货源；「绑定货源商品」可搜选改绑。
**若 tab 未出现**：查 `platformOptions` 是否被 `mergePlatforms` 覆盖（注册表接口 `/admin/platform/list` 返回 code=3）。

---

## Self-Review

- **Spec 覆盖**：数据链（Task 1/2/3）、导入（Task 3）、后台维护复用（Task 4）、幂等（Task 3 import upsert）、Phase 0 spike（Task 1）、测试（Task 3 纯 assert）均有任务。
- **占位符**：Task 1 Step 1/2 标注 `EDIT(Step1 回填)`——ISV 页面选择器**必须**先探路（spec §10 已列为 Phase 0），非遗忘型 TODO；其余步骤均有可运行代码。
- **类型一致**：`pdd_products.jsonl` 字段（`pdd_goods_id/item_id/title/price/images`）在 Task 2/3 一致；`build()` 签名在 Task 3 内一致；`source_product.source_product_code` 全程作为 1688 offerId 键。
- **未覆盖**：SKU 级关联、B/C = 非目标。
