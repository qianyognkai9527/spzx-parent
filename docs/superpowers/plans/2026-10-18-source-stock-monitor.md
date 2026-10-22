# 1688 货源库存全量监控 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让在卖的每一件淘宝商品，其 1688 货源没货/失效都能当天知道——全量建档 → 分级刷新库存 → 失效告警+页面标记（人工下架）→ ISV 同步提频并核验「没货→淘宝 0」。

**Architecture:** 复用现有链路扩围：`taobao_offer_map`(4190 绑定) 一次性建档进 `source_product`/`source_sku`（P1）；`detect_stock_change.py` 加 `--tiered` 分级池（T1 低库存每日 / T2 七天轮转 / T3 失效周检，P2）；`detect_alerts.py` 加 `source_dead` 规则 + 低库存页「货源失效」筛选（P3）；`isv_stock_sync.py` 一天三跑 + 行级核验表 `stock_sync_check`（P4）。

**Tech Stack:** Python 3.9 + Playwright async + CDP 9222（venv: `automation/venv/bin/python`）、PyMySQL（`dbconf.DB_CONFIG`）、Spring Boot 3.3.5 + MyBatis-Plus（spzx-model 实体 + spzx-manager mapper/service/controller）、Vue 3 + Element Plus（spzx-admin）、launchd LaunchAgent。

**Spec:** `docs/superpowers/specs/2026-10-18-source-stock-monitor-design.md`（决策记录 D1-D6 在其第 2 节）

## Global Constraints

- **禁止 `git commit` / `git add`**——本仓库交付永远不提交（owner 专属硬规则，覆盖一切模板里的 commit 步骤）。任务收尾 = 测试/一致性门通过 + `scripts/log_work.py` 留痕。
- Python 一律 `/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python`（下文简写 `$PY`）；脚本从 `automation/sourcing/` 目录跑（dbconf/cdp_utils 靠同目录 import）。
- MySQL CLI 一律 `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx`；`/tmp/spzx_my.cnf` 被清则先 `python3 scripts/mysql-cnf.py` 重建。
- Java 编译：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`；先 `mvn install -pl spzx-model -DskipTests -q` 再 `mvn compile -pl spzx-manager -am`。
- Java 单测禁裸 `mvn test`：`mvn test -pl spzx-manager -am -Dtest=<TestClass> -Dsurefire.failIfNoSpecifiedTests=false`。
- **动 `spzx-model` 实体后必须完整重启后端**：`scripts/stop-local.sh && scripts/start-local.sh`（jar 落后源码会自动重打包）。判活：`curl -m3 -o /dev/null -w '%{http_code}' localhost:8501/` 非 000。
- API 实测鉴权：`TK=$(redis-cli --raw keys 'user:login:*' | grep -v validatecode | head -1 | sed 's/user:login://')`，`curl -H "token: $TK" ...`。
- Python 单测走仓库惯例：`$PY test_xxx.py` 直跑（纯函数、无网络、不拉 Spring）。
- **Chrome 9222 纪律**：任务启动前守卫（CDP 在线 + 归类v2/品牌/规格匹配不在跑）；窗口模式 Chrome 勿重启；每商品 3-10s 间隔；风控（滑块/0 结果）冷却 25min。
- **crontab 不可程序化写入**（2026-10-07 实测挂死）：新增调度走 LaunchAgent；已存在的 crontab 行物理保留、改脚本内容退役。
- **plist 纪律**：读写用 `plutil -extract … -o -` / `PlistBuddy -c Print`（不带 `-o -` 的 `plutil -extract` 会原地覆写！）；改完 `plutil -lint` + `launchctl bootout/bootstrap gui/$(id -u)` + `launchctl print` 复核字段；同步仓库副本 `scripts/launchd/`（`cmp` 逐字节核）。
- 每期收尾 `python3 scripts/check-consistency.py`（先 `--selftest`）必须 0 fail；controller 端点变更必跑（AGENTS 门）。
- 新脚本里**不写任何 MySQL 口令**（一律 `from dbconf import DB_CONFIG`）。

---

### Task 1: source_status 加列（P1 前置）

**Files:**
- Create: `spzx-manager/src/main/resources/sql/source_status.sql`

**Interfaces:**
- Produces: `source_product.source_status TINYINT NULL`（1=正常 0=已失效 NULL=未检测）——P1 建档写入、P2 刷新维护、P3 后端/告警消费。

- [ ] **Step 1: 写迁移 SQL 文件**

```sql
-- source_status.sql (2026-10-18) 货源存活标记：库存监控闭环 P1 前置。
-- 1=正常 0=已失效(1688商品下架/打不开) NULL=未检测。写入方: backfill_offer_archive.py / detect_stock_change --tiered
ALTER TABLE source_product ADD COLUMN source_status TINYINT NULL COMMENT '货源存活:1=正常 0=已失效 NULL=未检测(2026-10-18库存监控)';
```

- [ ] **Step 2: 线上执行并验证**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx < spzx-manager/src/main/resources/sql/source_status.sql
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SHOW COLUMNS FROM source_product LIKE 'source_status';"
```
Expected: 一行 `source_status | tinyint(4) | YES | | NULL`。重复执行会报 Duplicate column——先查后执行即可。

---

### Task 2: 共享采集模块 offer_fetch.py（纯函数部分先测）

**Files:**
- Create: `automation/sourcing/offer_fetch.py`
- Test: `automation/sourcing/test_offer_fetch.py`

**Interfaces:**
- Produces:
  - `is_gone(text: str) -> bool`（GONE 判定，登录/风控页不算）
  - `parse_skus(payload_json_str: str) -> list[dict]`（keys: sku_key/sku_id/stock/price/spec_id）
  - `extract_meta(page_title: str, og_image: str|None) -> tuple[str, str|None]`（→ (title≤200字, img)）
  - `async fetch_offer(page, offer_id: str, settle: float = 3.0) -> dict`（keys: skus/gone/title/img；单页一次导航，监听器用完即删）

- [ ] **Step 1: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""offer_fetch 纯函数单测（仓库惯例：python 直跑，无网络）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from offer_fetch import is_gone, parse_skus, extract_meta  # noqa: E402


def test_is_gone():
    assert is_gone("很抱歉，您查看的商品已下架")
    assert is_gone("宝贝已下架 or 商品不存在")
    assert not is_gone("正常商品标题 库存999件")           # 正常页不算
    assert not is_gone("请登录后查看")                     # 登录页≠下架（collect_1688_full 同款守卫）
    assert not is_gone("安全验证")                         # 风控页≠下架
    assert not is_gone("")
    assert not is_gone(None)


def test_parse_skus():
    payload = '{"data":{"skuSelectorBizModel":{"skuInfoMap":{"M &gt; 白":{"skuId":"111","canBookCount":5,"price":12.5,"specId":"s1"},"XL 红":{"skuId":"222","canBookCount":0,"price":13,"specId":"s2"}}}}}'
    skus = parse_skus(payload)
    assert skus[0]["sku_key"] == "M > 白" and skus[0]["stock"] == 5
    assert skus[1]["stock"] == 0 and skus[1]["sku_id"] == "222"
    assert parse_skus("不是json") == []
    assert parse_skus('{"data":{}}') == []


def test_extract_meta():
    title, img = extract_meta("纯欲蕾丝睡裙-阿里巴巴", "https://cbu01.alicdn.com/x.jpg")
    assert title == "纯欲蕾丝睡裙" and img.endswith(".jpg")
    # 没有分隔符的标题原样保留；超 200 截断
    assert extract_meta("无分隔标题", None)[0] == "无分隔标题"
    long_t = "字" * 300
    assert len(extract_meta(long_t, None)[0]) == 200


if __name__ == "__main__":
    test_is_gone(); test_parse_skus(); test_extract_meta()
    print("test_offer_fetch: 3/3 PASS")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd automation/sourcing && $PY test_offer_fetch.py`
Expected: `ModuleNotFoundError: No module named 'offer_fetch'`

- [ ] **Step 3: 实现 offer_fetch.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1688 offer 详情页一次性采集（库存监控闭环共享模块，2026-10-18）。

一次导航同时拿：SKU API(canBookCount) + 页面正文(失效判定) + 标题/主图(建档用)。
detect_stock_change.fetch_source_skus 只抓 SKU 判不了死活；collect_1688_full 有判定但不复用结构。
消费者：backfill_offer_archive.py（P1 建档）、detect_stock_change --tiered（P2 刷新）。
"""
import asyncio
import json

SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
# 与 download_1688_materials.GONE_HINTS 同口径；collect_1688_full.py:90 的守卫：登录/风控页不算下架
GONE_HINTS = ("商品已下架", "宝贝已下架", "该商品已下架", "商品不存在", "页面不存在")


def is_gone(text):
    if not text:
        return False
    if "登录" in text or "验证" in text:
        return False
    return any(h in text for h in GONE_HINTS)


def parse_skus(payload):
    """queryofferskuselectormodel 响应体 -> SKU 列表（detect_stock_change 同款字段）。"""
    try:
        data = json.loads(payload)
        info = data.get("data", {}).get("skuSelectorBizModel", {}).get("skuInfoMap", {})
    except Exception:
        return []
    out = []
    for key, sv in info.items():
        if not isinstance(sv, dict):
            continue
        try:
            out.append({
                "sku_key": key.replace("&gt;", ">"),
                "sku_id": str(sv.get("skuId", "")),
                "stock": int(sv.get("canBookCount", 0)),
                "price": float(sv.get("price", 0)),
                "spec_id": str(sv.get("specId", "")),
            })
        except (TypeError, ValueError):
            continue
    return out


def extract_meta(page_title, og_image):
    """页面 <title> -> 商品名（取分隔符前段，≤200 字）；og:image -> 主图。"""
    t = (page_title or "").strip()
    for sep in (" - 阿里巴巴", "-阿里巴巴", " - 1688.com", "-1688.com"):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t[:200], (og_image or None)


async def fetch_offer(page, offer_id, settle=3.0):
    """开详情页一次，返回 {skus, gone, title, img}。调用方负责 wait_for 超时与异常。"""
    captured = {}

    async def on_resp(r):
        if SKU_API in r.url:
            try:
                captured["body"] = await r.text()
            except Exception:
                pass

    page.on("response", on_resp)
    try:
        await page.goto(f"https://detail.1688.com/offer/{offer_id}.html", wait_until="domcontentloaded")
        await asyncio.sleep(settle)
        body = await page.evaluate("()=>document.body?document.body.innerText:''")
        title = await page.title()
        img = await page.evaluate(
            "()=>{const m=document.querySelector('meta[property=\"og:image\"]');return m?m.content:null}")
        return {"skus": parse_skus(captured.get("body", "")), "gone": is_gone(body),
                **dict(zip(("title", "img"), extract_meta(title, img)))}
    finally:
        page.remove_listener("response", on_resp)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd automation/sourcing && $PY test_offer_fetch.py`
Expected: `test_offer_fetch: 3/3 PASS`

---

### Task 3: backfill_offer_archive.py（补映射 + 建档）

**Files:**
- Create: `automation/sourcing/backfill_offer_archive.py`
- Test: `automation/sourcing/test_backfill_offer_archive.py`

**Interfaces:**
- Consumes: `offer_fetch.fetch_offer`（Task 2）、`detect_stock_change.process_changes`（插入 source_sku，已存在）、`detect_stock_change.load_progress/save_progress`（写 detect_stock_pool_progress.json，已存在）。
- Produces: `build_product_row(offer_id, offer) -> tuple`（source_product INSERT 参数元组，Task 3 主流程与单测共用）；`remap(conn) -> int`；报告文件 `automation/sourcing/backfill_report.json`（keys: remapped/created/dead/failed/ts）。

- [ ] **Step 1: 写失败测试（纯函数：INSERT 参数与 offer_id 抽取）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backfill_offer_archive import build_product_row, OFFER_RE  # noqa: E402


def test_offer_re():
    assert OFFER_RE.search("https://detail.1688.com/offer/980287802829.html").group(1) == "980287802829"
    assert OFFER_RE.search("https://detail.1688.com/page/index.htm") is None


def test_build_product_row_alive():
    offer = {"skus": [{"sku_key": "M", "stock": 5, "price": 12.5}],
             "gone": False, "title": "测试睡裙", "img": "https://x/y.jpg"}
    row = build_product_row("980287802829", offer)
    # (name, code, url, price, freight, img, source_status, data_source, platform_type)
    assert row[0] == "测试睡裙" and row[1] == "980287802829"
    assert row[2].endswith("/offer/980287802829.html")
    assert row[3] == 12.5 and row[4] == 8          # 货源价=最低SKU价; 运费定值8(D4)
    assert row[6] == 1 and row[7] == 2 and row[8] == 1   # source_status=1, data_source=2, platform_type=1


def test_build_product_row_gone():
    offer = {"skus": [], "gone": True, "title": "已下架商品", "img": None}
    row = build_product_row("123", offer)
    assert row[6] == 0                              # 死链建档但标记失效
    assert row[3] == 0                              # 无价格记 0，不猜


if __name__ == "__main__":
    test_offer_re(); test_build_product_row_alive(); test_build_product_row_gone()
    print("test_backfill_offer_archive: 3/3 PASS")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd automation/sourcing && $PY test_backfill_offer_archive.py`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 backfill_offer_archive.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backfill_offer_archive.py — 补映射 + 全量建档（spec 2026-10-18 P1）。

用法:
  $PY backfill_offer_archive.py --remap          # 步骤1: URL正则补映射, 零采集
  $PY backfill_offer_archive.py --dry-run --limit 3
  $PY backfill_offer_archive.py --limit 500      # 步骤2: 建档, todo 按 DB 现算(映射即进度)
  $PY backfill_offer_archive.py --limit 500 --delay 8 --cooldown 1500
守卫(启动前必查): Chrome 9222 在线、归类v2/品牌/规格匹配不在跑。
纪律: 3-10s/个、风控冷却 25min、夜间轮次避开周六凌晨(collect_full 退役前)。
"""
import argparse, asyncio, json, re, sys, time, traceback
from datetime import datetime

import pymysql

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG
from cdp_utils import connect_cdp, new_page_quiet
from offer_fetch import fetch_offer
from detect_stock_change import process_changes, load_progress, save_progress

OFFER_RE = re.compile(r"offer/(\d+)")
CDP_PORT = 9222
REPORT = '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/backfill_report.json'


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_report():
    try:
        return json.load(open(REPORT, encoding='utf-8'))
    except Exception:
        return {"remapped": 0, "created": 0, "dead": [], "failed": [], "ts": None}


def save_report(rep):
    rep["ts"] = time.strftime("%F %T")
    json.dump(rep, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def build_product_row(offer_id, offer):
    """source_product INSERT 参数: (name, code, url, source_price, freight_cost, head_img, source_status, data_source, platform_type)"""
    skus = offer.get("skus") or []
    price = min((s["price"] for s in skus if s.get("price")), default=0)
    status = 0 if offer.get("gone") else 1
    title = offer.get("title") or f"1688货源{offer_id}"
    return (title, offer_id, f"https://detail.1688.com/offer/{offer_id}.html",
            price, 8, offer.get("img"), status, 2, 1)


def remap(conn):
    """URL 正则补映射：source_product_url 抽 offer_id 回填 taobao_offer_map.source_product_id。"""
    cur = conn.cursor()
    cur.execute("SELECT id, source_product_url FROM source_product WHERE is_deleted=0 AND source_product_url LIKE '%detail.1688.com/offer/%'")
    offer2pid = {}
    for pid, url in cur.fetchall():
        m = OFFER_RE.search(url or "")
        if m:
            offer2pid[m.group(1)] = pid
    cur.execute("SELECT id, offer_id FROM taobao_offer_map WHERE source_product_id IS NULL")
    todo = [(mid, oid) for mid, oid in cur.fetchall() if str(oid) in offer2pid]
    for mid, oid in todo:
        cur.execute("UPDATE taobao_offer_map SET source_product_id=%s, update_time=NOW() WHERE id=%s",
                    (offer2pid[str(oid)], mid))
    conn.commit()
    cur.close()
    return len(todo)


def todo_offers(conn, limit):
    """仍无档的绑定 offer：映射即进度——建过档的 source_product_id 已非空自然退出 todo。"""
    cur = conn.cursor()
    cur.execute("SELECT offer_id FROM taobao_offer_map WHERE source_product_id IS NULL ORDER BY offer_id" +
                (f" LIMIT {int(limit)}" if limit else ""))
    rows = [str(r[0]) for r in cur.fetchall()]
    cur.close()
    return rows


def archive_one(conn, offer_id, offer):
    """建档: INSERT source_product(死链也建,source_status=0) -> 回填映射 -> 存活时插SKU -> 写detect进度。"""
    row = build_product_row(offer_id, offer)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute("""INSERT INTO source_product
        (source_product_name, source_product_code, source_product_url, source_price, freight_cost,
         head_img_url, source_status, data_source, platform_type, crawl_time, create_time, is_deleted)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)""", row + (now, now))
    pid = cur.lastrowid
    cur.execute("UPDATE taobao_offer_map SET source_product_id=%s, update_time=NOW() WHERE offer_id=%s", (pid, offer_id))
    conn.commit()
    cur.close()
    if row[6] == 1 and offer.get("skus"):
        process_changes(pid, offer["skus"])       # 复用 detect_stock_change 的 SKU 插入(旧快照为空=全新插入)
    checked = load_progress()
    checked[pid] = now[:10]                        # 建档=今天已刷过, 免得 P2 T1 把 3000 个新档全当"从未刷新"
    save_progress(checked)
    return pid


async def run_backfill(args):
    conn = pymysql.connect(**DB_CONFIG)
    todo = todo_offers(conn, args.limit)
    log(f"待建档 {len(todo)} 个 offer")
    if args.dry_run:
        for oid in todo[:5]:
            log(f"  DRY 将采集 offer={oid}")
        conn.close(); return 0
    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["taobao.com", "1688.com"], log=log, minimize=True)
    page = await new_page_quiet(ctx)
    rep = load_report()
    done = failed = 0
    try:
        for oid in todo:
            try:
                offer = await asyncio.wait_for(fetch_offer(page, oid, settle=3.0), timeout=25)
                pid = archive_one(conn, oid, offer)
                rep["created"] += 1
                if offer.get("gone"):
                    rep["dead"].append(oid)
                    log(f"  ☠ offer={oid} 已失效, 建档 sp={pid} source_status=0")
                else:
                    log(f"  ✓ offer={oid} 建档 sp={pid}, {len(offer.get('skus') or [])} SKU")
            except Exception as e:
                failed += 1
                rep["failed"].append(oid)
                log(f"  ✗ offer={oid}: {str(e)[:80]}")
            done += 1
            if done % 20 == 0:
                save_report(rep)
                log(f"进度 {done}/{len(todo)} created={rep['created']} dead={len(rep['dead'])} failed={failed}")
            await asyncio.sleep(args.delay)
    finally:
        save_report(rep)
        try: await page.close()
        except Exception: pass
        try: await b.close()
        except Exception: pass
    conn.close()
    log(f"完成: created={rep['created']} dead={len(rep['dead'])} failed={failed}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remap", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        if args.remap:
            conn = pymysql.connect(**DB_CONFIG)
            n = remap(conn)
            conn.close()
            log(f"补映射回填 {n} 行")
            return
        rc = asyncio.get_event_loop().run_until_complete(run_backfill(args))
    except Exception:
        traceback.print_exc(); rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd automation/sourcing && $PY test_backfill_offer_archive.py`
Expected: `test_backfill_offer_archive: 3/3 PASS`

- [ ] **Step 5: 小样实测**

```bash
cd automation/sourcing
pgrep -f assign_shop_category_v2; pgrep -f edit_brand_title_batch; pgrep -f isv_sku_match   # 都必须为空
$PY backfill_offer_archive.py --remap                      # 补映射, 记下回填行数
$PY backfill_offer_archive.py --dry-run --limit 3          # DRY 打印 3 个 offer
$PY backfill_offer_archive.py --limit 3                    # 真采 3 个
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SELECT id,source_product_code,source_status,source_price,freight_cost FROM source_product WHERE data_source=2 ORDER BY id DESC LIMIT 5;"
```
Expected: 3 个 offer 建档成功、`source_status=1`、`freight_cost=8`、映射表 source_product_id 已回填；抽 1 个 offer 对 1688 页面人工核对 SKU 数与库存一致。

---

### Task 4: 跑完 P1 全量建档（运行任务，2-4 晚）

**Files:**
- 产物: `automation/sourcing/backfill_report.json`

- [ ] **Step 1: 夜间分段跑（避开周六凌晨）**

```bash
cd automation/sourcing
nohup $PY backfill_offer_archive.py --delay 6 > /tmp/backfill_run.log 2>&1 &
# 每晚跑完(或第二天)检查进度; todo 自然收缩, 断点续跑=直接再起
tail -5 /tmp/backfill_run.log
```
每晚重复直到 `待建档 0 个`。预计 ~3200 个 × (6s+8s) ≈ 3 晚。风控(连续 failed 或 0 SKU)时停 25min 再续。

- [ ] **Step 2: 验收**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT COUNT(*) total, SUM(source_product_id IS NULL) unmapped FROM taobao_offer_map;
SELECT source_status, COUNT(*) FROM source_product WHERE data_source=2 GROUP BY source_status;"
```
Expected: `unmapped` ≈ 0（采集失败除外，核对 failed 清单）；`data_source=2` 行数 = 补映射 + 新建档；dead 清单 ≥0 行。
**Dead 清单即时交付 owner**（这就是当下超卖风险名单），格式：offer_id + 绑定的 taobao_item_id + 标题。

- [ ] **Step 3: 核查 grade_quality 对新档的波及（spec 风险表）**

```bash
cd automation/sourcing && grep -n "data_source" grade_quality.py
```
若 grade_quality 的评级 SQL 会把 ~3200 个 `data_source=2` 新档卷入全量重算（05:30 的 DB 任务变慢/评级口径不符），在其池子 SQL 排除 `data_source=2` 并向 owner 报备一行；行为正常则只记录结论。

- [ ] **Step 4: 留痕**

```bash
python3 scripts/log_work.py --module 其它 --title "1688货源全量建档(P1)" --progress-file automation/sourcing/backfill_report.json --merge
```

---

### Task 5: detect_stock_change --tiered 分级刷新

**Files:**
- Modify: `automation/sourcing/detect_stock_change.py`（新增 tiered 模式，不动既有 --pool-both 行为）
- Test: `automation/sourcing/test_tiered_selection.py`

**Interfaces:**
- Consumes: `offer_fetch.fetch_offer`（Task 2，替代本文件原 fetch_source_skus 用于 tiered 路径）。
- Produces: `select_tiered(universe, checked, min_stocks, dead_ids, day_of_year, t1_threshold=100, monday=False) -> tuple[list, list, list]`（(t1,t2,t3)，元素为 pid）；CLI `--tiered`；SUMMARY 行追加 `tier=t1:N,t2:N,t3:N`。

- [ ] **Step 1: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_stock_change import select_tiered  # noqa: E402

U = [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, "e")]

def test_t1_low_stock_and_never_checked():
    # 库存<100 → T1; 从未查过 → T1; 无SKU(NULL) → T1
    t1, t2, t3 = select_tiered(U, {2: "2026-10-17"}, {1: 50, 3: None}, set(), 100, 100)
    assert t1 == [1, 3, 4, 5] and t2 == [] and t3 == []

def test_t2_rotation():
    # 库存充足且查过 → 只在 (pid+doy)%7==0 时进 T2
    checked = {1: "2026-10-17", 2: "2026-10-17", 3: "2026-10-17", 4: "2026-10-17", 5: "2026-10-17"}
    min_stocks = {1: 500, 2: 800, 3: 300, 4: 999, 5: 200}
    t1, t2, t3 = select_tiered(U, checked, min_stocks, set(), day_of_year=0, t1_threshold=100)
    assert t1 == []
    assert t2 == [p for p in (1, 2, 3, 4, 5) if p % 7 == 0]      # doy=0 → pid%7==0
    _, t2b, _ = select_tiered(U, checked, min_stocks, set(), day_of_year=1, t1_threshold=100)
    assert t2b == [p for p in (1, 2, 3, 4, 5) if (p + 1) % 7 == 0]

def test_t3_dead_only_on_monday():
    checked = {1: "2026-10-17"}
    t1, t2, t3 = select_tiered(U, checked, {1: 500}, {2, 3}, 100, 100, monday=False)
    assert 2 not in t1 + t2 + t3 and 3 not in t1 + t2 + t3        # 非周一死链不占额度
    t1, t2, t3 = select_tiered(U, checked, {1: 500}, {2, 3}, 100, 100, monday=True)
    assert t3 == [2, 3]

if __name__ == "__main__":
    test_t1_low_stock_and_never_checked(); test_t2_rotation(); test_t3_dead_only_on_monday()
    print("test_tiered_selection: 3/3 PASS")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd automation/sourcing && $PY test_tiered_selection.py`
Expected: `ImportError: cannot import name 'select_tiered'`

- [ ] **Step 3: 实现（detect_stock_change.py 追加）**

在 `POOL_SQL` 后追加宇宙 SQL，在 `due_by_staleness` 后追加纯函数与 tiered 主流程：

```python
# 分级刷新宇宙：铺货绑定的货源（淘宝映射 ∪ 平台商品绑定），不带绑定的纯选品候选不进日常刷新
TIERED_SQL = (
    "SELECT DISTINCT sp.id, sp.source_product_url FROM source_product sp "
    "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
    "AND ( EXISTS (SELECT 1 FROM taobao_offer_map tm WHERE tm.source_product_id = sp.id) "
    "   OR EXISTS (SELECT 1 FROM product_bind_relation br WHERE br.source_productId = sp.id AND br.is_deleted = 0))"
)
MIN_STOCK_SQL = (
    "SELECT source_product_id, MIN(stock) FROM source_sku "
    "WHERE is_deleted=0 AND status=1 AND stock IS NOT NULL GROUP BY source_product_id"
)


def select_tiered(universe, checked, min_stocks, dead_ids, day_of_year, t1_threshold=100, monday=False):
    """返回 (t1, t2, t3)。T1=低库存/从未刷新/无SKU 每日刷；T2=其余按 (pid+doy)%7 每周一天；
    T3=失效周检(仅周一)。纯函数，日期无关可测。"""
    t1, t2, t3 = [], [], []
    for pid, _oid in universe:
        pid = int(pid)
        if pid in dead_ids:
            if monday:
                t3.append(pid)
            continue
        ms = min_stocks.get(pid)
        if (ms is not None and ms < t1_threshold) or ms is None or pid not in checked:
            t1.append(pid)
            continue
        if (pid + int(day_of_year)) % 7 == 0:
            t2.append(pid)
    return t1, t2, t3
```

`main()` 里加 `--tiered` 分支（在 `products = load_products(...)` 之前分流，复用既有的 Playwright 循环与 SUMMARY 打印）：

```python
    elif a == "--tiered":
        pass  # 标记位，见下
```
解析后：
```python
    tiered = "--tiered" in sys.argv
    if tiered:
        conn = pymysql.connect(**DB_CONFIG); cur = conn.cursor()
        cur.execute(TIERED_SQL); universe = [(int(p), re.search(r"offer/(\d+)", u or "").group(1) if re.search(r"offer/(\d+)", u or "") else None) for p, u in cur.fetchall() if re.search(r"offer/(\d+)", u or "")]
        cur.execute(MIN_STOCK_SQL); min_stocks = {int(r[0]): int(r[1]) for r in cur.fetchall()}
        cur.execute("SELECT id FROM source_product WHERE is_deleted=0 AND source_status=0")
        dead_ids = {int(r[0]) for r in cur.fetchall()}
        conn.close()
        checked = load_progress()
        import datetime as _dt
        monday = datetime.now().weekday() == 0
        t1, t2, t3 = select_tiered(universe, checked, min_stocks, dead_ids,
                                   _dt.date.today().timetuple().tm_yday, t1_threshold=t1_threshold, monday=monday)
        todo = t1 + t2 + t3
        # 硬停钟：05:00 后不再开新页（把 9222 让给 05:30 ISV 同步）
        if not test and not limit:
            todo = todo[:max_per_run]
        log(f"tiered: T1={len(t1)} T2={len(t2)} T3={len(t3)} 本轮={len(todo)}")
        products = todo   # 后续循环逐个 (pid, offer_id) 需要 offer_id → universe 建 dict
        oid_of = dict(universe)
        todo = [(pid, oid_of[pid]) for pid in todo]
        # ↓ 跳过既有 due_by_staleness 过滤（分级逻辑已含），直接进 Playwright 循环
```
循环体内（抓取成功后）追加失效标记：
```python
                if skus:
                    conn2 = pymysql.connect(**DB_CONFIG); c2 = conn2.cursor()
                    c2.execute("UPDATE source_product SET source_status=1 WHERE id=%s AND (source_status IS NULL OR source_status=0)", (pid,))
                    conn2.commit(); c2.close(); conn2.close()
```
（tiered 路径的抓取改用 `offer_fetch.fetch_offer`：`res = await asyncio.wait_for(fetch_offer(page, oid), timeout=FETCH_TIMEOUT)`，`skus = res["skus"]`；`res["gone"]` 为真 → `UPDATE source_product SET source_status=0 WHERE id=%s` 且本轮不动 SKU。）
SUMMARY 行追加：`print(f"... tier=t1:{len(t1)},t2:{len(t2)},t3:{len(t3)}")`。
CLI 参数：`--t1-threshold`（默认 100）、`--max-per-run`（tiered 默认 600）、`--delay`（默认 5.0）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd automation/sourcing && $PY test_tiered_selection.py`
Expected: `test_tiered_selection: 3/3 PASS`
回归：`$PY detect_stock_change.py --test --pool-both --max-per-run 3`（旧路径行为不变，正常打印 SUMMARY）。

---

### Task 6: 调度迁移（03:00 LaunchAgent + 旧脚本退役 + 四副本对齐）

**Files:**
- Create: `automation/sourcing/run_stock_refresh.sh`、`~/Library/LaunchAgents/com.spzx.stock-refresh.plist`、仓库副本 `scripts/launchd/com.spzx.stock-refresh.plist`
- Modify: `automation/sourcing/inventory_cron.sh`（去采集）、`automation/sourcing/cron_collect_full.sh`（内置退役）、`automation/sourcing/task-progress-config.json`、注册表 `ingest_dataset`

**Interfaces:**
- Produces: LaunchAgent `com.spzx.stock-refresh`（每日 03:00）；注册表 `source_stock_change.cron_expr='0 3 * * *'`。

- [ ] **Step 1: 写 run_stock_refresh.sh**

```bash
#!/bin/bash
# 分级库存刷新（03:00，spec 2026-10-18 P2）。守卫同 inventory_cron。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/stock_refresh_cron.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=source_stock_change

skip() {
  echo "[$(date '+%m-%d %H:%M')] $1, 跳过本轮"
  $PY "$ALERT" --key stock_refresh --dataset "$DS" --msg "分级刷新未跑: $1" > /dev/null 2>&1
  local bid; bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || skip "Chrome 9222 不在线"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f detect_stock_change > /dev/null && skip "上一轮分级刷新未结束"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 分级刷新 开始 ===" >> $LOG
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
BID=$($PY "$BATCH" begin --dataset "$DS")
$PY detect_stock_change.py --tiered --max-per-run 600 --delay 5 >> $LOG 2>&1
rc=$?
SUMMARY=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | grep '^SUMMARY ' | tail -1)
CHECKED=$(echo "$SUMMARY" | sed -n 's/.*checked=\([0-9]*\).*/\1/p')
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 分级刷新 结束 rc=$rc ===" >> $LOG
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${CHECKED:-0}" --rows-ok "${CHECKED:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "detect_stock_change --tiered 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key stock_refresh --dataset "$DS" --type cron_failed --msg "分级刷新异常退出 rc=$rc" > /dev/null 2>&1
fi
```

- [ ] **Step 2: 写 plist（照 com.spzx.stock-sync.plist 结构，StartCalendarInterval Hour=3 Minute=0，StandardOutPath=/tmp/stock_refresh_launchd.log）**

- [ ] **Step 3: 加载并复核**

```bash
chmod +x automation/sourcing/run_stock_refresh.sh
plutil -lint ~/Library/LaunchAgents/com.spzx.stock-refresh.plist
launchctl bootout gui/$(id -u)/com.spzx.stock-refresh 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.stock-refresh.plist
launchctl print gui/$(id -u)/com.spzx.stock-refresh | grep -A3 'StartCalendarInterval\|ProgramArguments'
cp ~/Library/LaunchAgents/com.spzx.stock-refresh.plist scripts/launchd/ && cmp ~/Library/LaunchAgents/com.spzx.stock-refresh.plist scripts/launchd/com.spzx.stock-refresh.plist && echo COPY_OK
launchctl kickstart gui/$(id -u)/com.spzx.stock-refresh   # 立刻试跑一轮（白天跑会撞守卫→验证 skip 路径也算过）
sleep 10; tail -5 /tmp/stock_refresh_launchd.log /tmp/stock_refresh_cron.log
```

- [ ] **Step 4: inventory_cron.sh 去采集（crontab 行保留，内容改）**

删除第 32 行 `BID=$($PY "$BATCH" begin --dataset "$DS")` 与第 34-49 行（1. 采集块 + SUMMARY 解析 + CANDIDATES/CHECKED/CHANGED/DEFERRED），及第 60-72 行对 BID/rc 的 end/alert 逻辑；文件头加注释：
```bash
# [2026-10-18] 采集已迁 03:00 LaunchAgent com.spzx.stock-refresh（detect_stock_change --tiered）。
# 本脚本(crontab 05:00)只保留 detect_alerts 提醒检测。crontab 行不可程序化删除，物理保留。
```
保留部分骨架：守卫 → `echo ... 提醒检测开始` → ARB 批次 → detect_alerts → end/alert（原 51-59、73-78 行逻辑原样）。改完 `bash -n inventory_cron.sh` 语法过。

- [ ] **Step 5: cron_collect_full.sh 内置退役**

在第 10 行（DS=source_sku 之后）插入：
```bash
# [2026-10-18 退役] 被分级刷新取代（detect_stock_change --tiered，每日 03:00 LaunchAgent）。
# crontab 行不可程序化删除（2026-10-07 实测挂死），故脚本内置退役：进脚本即退出。
echo "[$(date '+%m-%d %H:%M')] collect_1688_full 已退役(被分级刷新取代), 跳过"
exit 0
```

- [ ] **Step 6: 注册表 + 卡片对齐**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "UPDATE ingest_dataset SET cron_expr='0 3 * * *' WHERE code='source_stock_change'; SELECT code,cron_expr FROM ingest_dataset WHERE code='source_stock_change';"
```
`task-progress-config.json` 的 `detect_stock_change` 条目：`launchCmd` 改 `... detect_stock_change.py --tiered --max-per-run 600`、tags 加 `"定时·每日03:00"`、schedule 字段（如有）改 `"每日 03:00"`。collect_1688_full 条目 name 前加「[已退役]」。

- [ ] **Step 7: 一致性门**

```bash
python3 scripts/check-consistency.py --selftest && python3 scripts/check-consistency.py
```
Expected: 0 fail（新增 stock_refresh 若被按"注册表有而机器无"报红，属预期核对项——把 run_stock_refresh.sh 登记进对应检查的白名单/清单后再跑到绿；改动本身进 plan 记录）。

---

### Task 7: detect_alerts source_dead 规则（P3-告警侧）

**Files:**
- Modify: `automation/sourcing/detect_alerts.py`
- Test: `automation/sourcing/test_detect_source_dead.py`

**Interfaces:**
- Consumes: `source_product.source_status`（Task 1）、`has_unread/insert_alert`（本文件已有）。
- Produces: `dead_alert_message(name, sp_id, item_ids) -> str`；`detect_source_dead(conn) -> int`；CLI `--type source_dead`（valid 集合加入）。

- [ ] **Step 1: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_alerts import dead_alert_message  # noqa: E402


def test_message_contains_names_and_items():
    m = dead_alert_message("瑰若睡裙", 123, [1071, 1072])
    assert "瑰若睡裙" in m and "123" in m and "1071" in m and "1072" in m
    assert "人工" in m          # D1: 失效只告警, 处理是人工
    m2 = dead_alert_message(None, 55, [])
    assert "55" in m2           # 无名货源回退 sp_id


if __name__ == "__main__":
    test_message_contains_names_and_items(); print("test_detect_source_dead: PASS")
```

- [ ] **Step 2: 跑测试确认失败** → `ImportError`

- [ ] **Step 3: 实现（detect_alerts.py 追加）**

```python
def dead_alert_message(sp_name, sp_id, item_ids):
    """source_dead 告警文案（纯函数）。D1 口径：只告警，下架人工做。"""
    name = sp_name or f"货源{sp_id}"
    msg = f"货源已失效(1688商品下架/打不开): {name}"
    if item_ids:
        msg += f" -> 淘宝商品 {','.join(str(x) for x in item_ids)}"
    msg += "，ISV同步推不动，请人工下架"
    return msg


def detect_source_dead(conn):
    """货源整个失效(source_status=0)且有淘宝绑定 -> source_dead；复活(source_status=1)自动销案(status=2)。"""
    cur = conn.cursor()
    created = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "SELECT a.id FROM sync_alert a JOIN source_product sp ON sp.id=a.source_product_id "
        "WHERE a.alert_type='source_dead' AND a.status=0 AND sp.source_status=1")
    for (aid,) in cur.fetchall():
        cur.execute("UPDATE sync_alert SET status=2 WHERE id=%s", (aid,))
        log(f"  [source_dead] 复活销案 alert={aid}")
    cur.execute(
        "SELECT sp.id, sp.source_product_name FROM source_product sp "
        "WHERE sp.is_deleted=0 AND sp.source_status=0 "
        "AND EXISTS (SELECT 1 FROM taobao_offer_map tm WHERE tm.source_product_id = sp.id)")
    for sp_id, sp_name in cur.fetchall():
        if has_unread(cur, "source_dead", source_product_id=sp_id):
            continue
        cur.execute("SELECT taobao_item_id FROM taobao_offer_map WHERE source_product_id=%s", (sp_id,))
        item_ids = [r[0] for r in cur.fetchall()]
        insert_alert(cur, "source_dead", dead_alert_message(sp_name, sp_id, item_ids),
                     source_product_id=sp_id)
        created += 1
        log(f"  [source_dead] sp={sp_id} {sp_name} -> items={item_ids}")
    conn.commit()
    cur.close()
    return created
```
`main()`：`valid` 集合加 `"source_dead"`；`if alert_type in ("source_dead", "all"):` 分支调用并计数。

- [ ] **Step 4: 跑测试确认通过** → `test_detect_source_dead: PASS`

- [ ] **Step 5: 实跑验证（P1 若有 dead 存量，这里应成批告警）**

```bash
cd automation/sourcing && $PY detect_alerts.py --type source_dead
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SELECT id,message FROM sync_alert WHERE alert_type='source_dead' AND status=0 ORDER BY id DESC LIMIT 5;"
```

---

### Task 8: 后端失效面（实体/VO/Mapper/Service/Controller + 测试）

**Files:**
- Modify: `spzx-model/.../entity/product/Product.java`、`spzx-model/.../vo/mall/LowStockRowVo.java`、`spzx-manager/.../mapper/LowStockMapper.java`、`spzx-manager/src/main/resources/mapper/LowStockMapper.xml`、`spzx-manager/.../service/LowStockService.java`、`spzx-manager/.../controller/LowStockController.java`
- Test: `spzx-manager/src/test/java/com/joker/spzx/manager/service/LowStockParamTest.java`

**Interfaces:**
- Produces: `LowStockService.normalizeDeadFilter(String) -> String`（"no"/"dead"，非法回 "no"）；`LowStockMapper.selectDeadGroups(IPage, @Param("keyword"), @Param("handleStatus"))`；`/admin/lowStock/list` 新查询参数 `sourceDead`；VO 新字段 `sourceStatus`。

- [ ] **Step 1: 写失败测试（LowStockParamTest 追加）**

```java
    @Test
    void 失效筛选仿facet白名单_非法回no() {
        assertEquals("no", LowStockService.normalizeDeadFilter(null));
        assertEquals("no", LowStockService.normalizeDeadFilter(""));
        assertEquals("no", LowStockService.normalizeDeadFilter("enjoy"));
        assertEquals("dead", LowStockService.normalizeDeadFilter("dead"));
        assertEquals("no", LowStockService.normalizeDeadFilter("Dead")); // 大小写敏感
        assertEquals("dead", LowStockService.normalizeDeadFilter(" dead "));
    }

    @Test
    void 失效分组查询必须钉住source_status和铺货过滤() {
        String xml = mapperXml();
        assertTrue(Pattern.compile(
                "<select id=\"selectDeadGroups\"[\\s\\S]*?sp\\.source_status\\s*=\\s*0[\\s\\S]*?EXISTS[\\s\\S]*?taobao_offer_map",
                Pattern.CASE_INSENSITIVE).matcher(xml).find(),
                "selectDeadGroups 必须只查 source_status=0 且带铺货 EXISTS，否则失效页混入健康/未铺货货源");
        assertTrue(Pattern.compile(
                "sp\\.source_status\\s+AS\\s+sourceStatus", Pattern.CASE_INSENSITIVE).matcher(xml).find(),
                "主查询必须带出 sourceStatus 供前端失效徽标");
    }
```

- [ ] **Step 2: 编译跑测试确认失败**

Run: `mvn install -pl spzx-model -DskipTests -q && mvn test -pl spzx-manager -am -Dtest=LowStockParamTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: 编译失败（normalizeDeadFilter 不存在）

- [ ] **Step 3: 实现**

Product.java 追加：
```java
    @Schema(description = "货源存活:1=正常 0=已失效 NULL=未检测(库存监控 2026-10-18)")
    @TableField("source_status")
    private Integer sourceStatus;
```
LowStockRowVo 追加：
```java
    /** 货源存活：1=正常 0=已失效（前端失效徽标）；NULL=未检测 */
    private Integer sourceStatus;
```
LowStockService 追加常量与归一化、`list` 加参数与分支：
```java
    /** 失效筛选：no=按阈值正常视图 dead=货源失效视图（非法回 no，仿 facet） */
    public static final Set<String> DEAD_FILTERS = Set.of("no", "dead");

    public static String normalizeDeadFilter(String raw) {
        if (raw == null) return "no";
        String v = raw.trim();
        return DEAD_FILTERS.contains(v) ? v : "no";
    }

    public IPage<LowStockRowVo> list(String thresholdParam, String keyword, String handleStatus,
                                     String sourceDead, Integer page, Integer size) {
        // threshold 归一化照旧（失效视图忽略阈值，但白名单照校验，避免静默放行）
        ...
        String deadFilter = normalizeDeadFilter(sourceDead);
        IPage<LowStockRowVo> groups = "dead".equals(deadFilter)
                ? lowStockMapper.selectDeadGroups(new Page<>(pageNum, pageSize), kw, normalizeHandleFilter(handleStatus))
                : lowStockMapper.selectLowStockGroups(new Page<>(pageNum, pageSize), threshold, kw, normalizeHandleFilter(handleStatus));
        // taobaoItems 回填两支共用；selectLowSpecs 只在非 dead 分支调
    }
```
LowStockMapper.java 追加：
```java
    /** 货源失效视图：source_status=0 的铺货货源（无 SKU 行也能进列表），lowSpecCount 恒 0 */
    IPage<LowStockRowVo> selectDeadGroups(IPage<LowStockRowVo> page,
                                          @Param("keyword") String keyword,
                                          @Param("handleStatus") String handleStatus);
```
LowStockMapper.xml：主查询 SELECT 列表加 `sp.source_status AS sourceStatus,`；追加：
```xml
    <!-- 货源失效视图（spec 2026-10-18 P3）：死链建档无 SKU 行，FROM source_sku 的主查询永远带不出，
         必须 source_product 驱动。低库存/失效是两个口径，本查询忽略库存阈值。 -->
    <select id="selectDeadGroups" resultType="com.joker.spzx.model.vo.mall.LowStockRowVo">
        SELECT sp.id                  AS sourceProductId,
               sp.source_product_name AS title,
               sp.source_product_url  AS sourceUrl,
               sp.source_status       AS sourceStatus,
               0                      AS lowSpecCount,
               h.handle_type          AS handleType,
               DATE_FORMAT(h.handle_time, '%Y-%m-%d %H:%i') AS handleTime
        FROM source_product sp
        LEFT JOIN low_stock_handle h ON h.source_product_id = sp.id
        WHERE sp.is_deleted = 0
          AND sp.source_status = 0
          AND EXISTS (
              SELECT 1 FROM taobao_offer_map tm
              WHERE tm.source_product_id = sp.id
          )
        <if test="handleStatus == 'pending'">
            AND h.source_product_id IS NULL
        </if>
        <if test="handleStatus == 'done'">
            AND h.source_product_id IS NOT NULL
        </if>
        <if test="keyword != null">
            AND sp.source_product_name LIKE CONCAT('%', #{keyword}, '%')
        </if>
        ORDER BY sp.id ASC
    </select>
```
LowStockController `/list` 加 `@RequestParam(required = false) String sourceDead` 并透传。

- [ ] **Step 4: 编译 + 测试通过**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn install -pl spzx-model -DskipTests -q && mvn test -pl spzx-manager -am -Dtest=LowStockParamTest -Dsurefire.failIfNoSpecifiedTests=false
```
Expected: BUILD SUCCESS，全部绿（含既有 8 条——sourceStatus 列与新增 select 不破坏旧钉子）。

- [ ] **Step 5: 完整重启 + API 实测**

```bash
scripts/stop-local.sh && scripts/start-local.sh
curl -m3 -o /dev/null -w '%{http_code}\n' localhost:8501/    # 非 000
TK=$(redis-cli --raw keys 'user:login:*' | grep -v validatecode | head -1 | sed 's/user:login://')
curl -s -H "token: $TK" 'localhost:8501/admin/lowStock/list?sourceDead=dead&page=1&size=5' | head -c 400
curl -s -H "token: $TK" 'localhost:8501/admin/lowStock/list?sourceDead=dead&threshold=99&page=1' -o /dev/null -w '%{http_code}\n'   # threshold 白名单外仍 400
```
Expected: dead 视图返回 Task 4 的失效清单（records 里 sourceStatus=0）；非法 threshold 仍 400。

---

### Task 9: 前端失效面（lowStock.vue）

**Files:**
- Modify: `/Users/qyk9527/webstormProject/spzx-admin/src/views/mall/lowStock.vue`

- [ ] **Step 1: 工具栏加筛选（handleStatus 组之后）**

```html
        <el-radio-group v-model="query.sourceDead" size="small" @change="onSearch">
          <el-radio-button value="no">库存视图</el-radio-button>
          <el-radio-button value="dead">货源失效</el-radio-button>
        </el-radio-group>
```

- [ ] **Step 2: query/URL/load 三处接线**

```js
const sourceDeadFromUrl = () => (['no', 'dead'].includes(route.query.sourceDead) ? route.query.sourceDead : 'no')
// query 加: sourceDead: sourceDeadFromUrl(),
// load() 参数加: sourceDead: query.sourceDead,
// syncUrl() 加: sourceDead: query.sourceDead === 'no' ? undefined : query.sourceDead,
```

- [ ] **Step 3: 失效徽标（货源标题列内）**

```html
<template #default="{ row }">
  <el-tag v-if="row.sourceStatus === 0" type="danger" size="small" class="dead-tag">失效</el-tag>
  {{ row.title || ('offer ' + (row.offerId ?? row.sourceProductId)) }}
</template>
```
样式 `.dead-tag { margin-right: 6px; }`。hint 文案补一句「货源失效=1688已下架/打不开，ISV同步推不动，请尽快人工下架」。

- [ ] **Step 4: 冒烟**

```bash
curl -s localhost:3001/src/views/mall/lowStock.vue | head -5     # vite dev 正常返回模块源码
```
浏览器人工过一遍：库存视图↔失效视图切换、URL 带 sourceDead=dead 刷新不丢、失效行有红标、处理按钮可用。

---

### Task 10: stock_sync_check 表 + isv_sync_verify.py（P4-核验机制）

**Files:**
- Create: `spzx-manager/src/main/resources/sql/stock_sync_check.sql`、`automation/sourcing/isv_sync_verify.py`
- Test: `automation/sourcing/test_isv_sync_verify.py`

**Interfaces:**
- Consumes: `scrape_isv_offer_taobao` 的 `get_frame/open_page/nav_to_guanli/chip/query`（isv_sku_match 同款「已关联货源 chip + 搜索框搜 ID」路径）、`dbconf`。
- Produces: 表 `stock_sync_check`；`parse_sync_record(text) -> (verdict, numbers)`（1=成功同步为0/若干、2=无记录、3=失败）；`async verify_items(conn, item_ids, dry=False) -> list[dict]`；CLI `--cap N --dry-run`。

- [ ] **Step 1: DDL**

```sql
-- stock_sync_check.sql (2026-10-18) ISV 同步 0 库存行级核验（spec P4）。
CREATE TABLE IF NOT EXISTS stock_sync_check (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  check_time DATETIME NOT NULL,
  taobao_item_id BIGINT NOT NULL,
  offer_id BIGINT NULL,
  record_text TEXT NULL,
  verdict TINYINT NOT NULL COMMENT '1=成功同步为0 2=无同步记录 3=失败/异常',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_time (check_time),
  KEY idx_item (taobao_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ISV同步0库存行级核验';
```
执行：`/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx < spzx-manager/src/main/resources/sql/stock_sync_check.sql`

- [ ] **Step 2: 写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isv_sync_verify import parse_sync_record  # noqa: E402


def test_parse_sync_record():
    v, n = parse_sync_record("商品库存同步为352，M 白色规格库存同步为286")
    assert v == 1 and n == [352, 286]
    v, n = parse_sync_record("商品库存同步为0")
    assert v == 1 and n == [0]
    assert parse_sync_record("同步失败：网络异常")[0] == 3
    assert parse_sync_record("今天天气不错")[0] == 2
    assert parse_sync_record("")[0] == 2
    assert parse_sync_record(None)[0] == 2

if __name__ == "__main__":
    test_parse_sync_record(); print("test_isv_sync_verify: PASS")
```

- [ ] **Step 3: 跑测试确认失败 → 实现 isv_sync_verify.py**

核心逻辑（模态框处理复用 isv_stock_sync 的 `wait_no_modal` 模式）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isv_sync_verify.py — ISV 同步后 0 库存行级核验（spec 2026-10-18 P4）。

对本地 0 库存且存活的绑定商品逐个开控制台行级「同步记录」弹窗，
证明「1688没货 → 淘宝被推成0」真实发生；无记录/失败写告警。
用法: $PY isv_sync_verify.py --cap 50 [--dry-run]
"""
import argparse, asyncio, random, re, sys, time, traceback
import pymysql
sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG
from cdp_utils import connect_cdp
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli
import isv_sku_match as M
import isv_stock_sync as S   # wait_no_modal 等复用


def log(m):
    M.log(m)


def parse_sync_record(text):
    """行级同步记录文本 -> (verdict, numbers)。纯函数。"""
    if not text:
        return (2, [])
    if "失败" in text or "异常" in text:
        return (3, [])
    nums = [int(n) for n in re.findall(r"同步为\s*(\d+)", text)]
    return (1, nums) if nums else (2, [])


def zero_stock_targets(conn, cap):
    """本地 0 库存活绑定商品（任一 SKU stock=0 即危险）+ 对照随机 10 个非零。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT tm.taobao_item_id, tm.offer_id FROM taobao_offer_map tm "
        "JOIN source_product sp ON sp.id = tm.source_product_id AND sp.is_deleted=0 AND sp.source_status=1 "
        "WHERE EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.is_deleted=0 "
        "AND ss.status=1 AND ss.stock=0) LIMIT %s", (cap,))
    zeros = cur.fetchall()
    cur.execute(
        "SELECT tm.taobao_item_id, tm.offer_id FROM taobao_offer_map tm "
        "JOIN source_product sp ON sp.id = tm.source_product_id AND sp.is_deleted=0 AND sp.source_status=1 "
        "AND EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.is_deleted=0 "
        "AND ss.status=1 AND ss.stock>0) ORDER BY RAND() LIMIT 10")
    control = cur.fetchall()
    cur.close()
    return zeros, control


async def read_row_sync_record(fr, item_id):
    """控制台「已关联货源」chip + 搜索框搜 itemId -> 打开该行「同步记录」弹窗 -> 返回文本。"""
    # chip + query 复用 scrape_isv_offer_taobao 既有函数（先点 chip 再搜，默认视图搜不到）
    ...
    # 行内「同步记录」按钮: fr.locator('.ant-table-row', has_text=str(item_id)).locator('text=同步记录').click()
    # 文本: .ant-modal:not([style*="display: none"]) .ant-modal-body innerText
    # 读完关闭弹窗（S.wait_no_modal 兜底）
    return text


async def verify_items(conn, targets, dry=False):
    b, ctx = await connect_cdp(9222, keep_urls=["taobao.com", "1688.com"], log=log, minimize=True)
    page = await open_page(ctx, quiet=True)
    fr = await get_frame(page)
    results = []
    now = time.strftime("%F %T")
    try:
        cur = conn.cursor()
        for item_id, offer_id in targets:
            try:
                text = await read_row_sync_record(fr, str(item_id))
                verdict, nums = parse_sync_record(text)
            except Exception as e:
                text, verdict, nums = str(e)[:200], 3, []
            results.append({"item": item_id, "offer": offer_id, "verdict": verdict,
                            "text": (text or "")[:500], "nums": nums})
            if not dry:
                cur.execute(
                    "INSERT INTO stock_sync_check (check_time, taobao_item_id, offer_id, record_text, verdict) "
                    "VALUES (%s,%s,%s,%s,%s)", (now, item_id, offer_id, text, verdict))
            await asyncio.sleep(2)
        conn.commit()
        cur.close()
    finally:
        try: await page.close()
        except Exception: pass
        try: await b.close()
        except Exception: pass
    return results


def alert_failures(conn, results):
    """0 库存目标的 verdict 2/3 → sync_alert（按天去重：同 item 未读不重复）。"""
    cur = conn.cursor()
    for r in results:
        if r["verdict"] == 1:
            continue
        cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type='isv_sync_fail' AND status=0 "
                    "AND message LIKE %s", (f"%{r['item']}%",))
        if cur.fetchone()[0]:
            continue
        msg = f"ISV库存核验异常: 淘宝商品{r['item']} 0库存但同步记录{'缺失' if r['verdict']==2 else '失败'}: {r['text'][:120]}"
        cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES ('isv_sync_fail',%s,0,%s)",
                    (msg, time.strftime("%F %T")))
    conn.commit()
    cur.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        conn = pymysql.connect(**DB_CONFIG)
        zeros, control = zero_stock_targets(conn, args.cap)
        log(f"0库存目标 {len(zeros)} + 对照 {len(control)}")
        results = asyncio.get_event_loop().run_until_complete(verify_items(conn, zeros + control, args.dry_run))
        bad = [r for r in results if r["verdict"] != 1 and r in zeros]
        log(f"核验完成: 0库存判定 1={sum(1 for r in results if r['verdict']==1)} 2={...} 3={...}")
        if not args.dry_run:
            alert_failures(conn, [r for r in results if r["verdict"] != 1])
        conn.close()
    except Exception:
        traceback.print_exc(); sys.exit(1)

if __name__ == "__main__":
    main()
```
（`read_row_sync_record` 的 chip/query 与行定位按 `isv_sku_match.open_match_drawer` 同款选择器写全；`main` 里 `2={...} 3={...}` 展开为同款计数表达式。）

- [ ] **Step 4: 跑测试确认通过** → `test_isv_sync_verify: PASS`

---

### Task 11: 0 库存探针（门禁，不过就停）

- [ ] **Step 1: 找一个真实 0 库存活目标**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "
SELECT tm.taobao_item_id, tm.offer_id, sp.source_product_name FROM taobao_offer_map tm
JOIN source_product sp ON sp.id=tm.source_product_id AND sp.source_status=1
WHERE EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.status=1 AND ss.is_deleted=0 AND ss.stock=0)
LIMIT 5;"
```

- [ ] **Step 2: 单件实测（交互盯守）**

```bash
cd automation/sourcing && $PY isv_stock_sync.py --pages 1 --dry-run   # 热身确认控制台可达
$PY isv_sync_verify.py --cap 1
```
Expected: `stock_sync_check` 出现该 item 的行级记录。**判定**：
- record_text 含「同步为 0」→ verdict 1 → **门禁通过**，继续 Task 12；
- verdict 2/3（ISV 不推 0/推失败）→ **停下**：`page.screenshot()` 留证、汇总 record_text，向 owner 报告实测结果并等重新决策（spec D1 后备方案预案：自动改淘宝库存）。
- 若本地无任何 0 库存目标：改用最低库存商品验证「同步为 N 且 N=本地库存」（机制等价证明），并在报告中注明「0 推送行为待首个自然 0 库存出现时补证」。

- [ ] **Step 3: 留痕**：探针结果（含截图路径/record_text）写 log_work。

---

### Task 12: ISV 提频到 05:30/12:30/19:30 + 每轮核验接线

**Files:**
- Modify: `~/Library/LaunchAgents/com.spzx.stock-sync.plist` + 仓库副本 `scripts/launchd/com.spzx.stock-sync.plist`、`automation/sourcing/run_stock_sync.sh`

- [ ] **Step 1: run_stock_sync.sh 接核验（rc=0 且非 dry 分支内，BATCH end 之前）**

```bash
  # 行级核验（spec P4）：0库存商品的同步记录抽查，写 stock_sync_check，异常写告警
  $PY isv_sync_verify.py --cap 50 >> $LOG 2>&1 || true
```
另加守卫（与 refresh 互斥）：
```bash
pgrep -f detect_stock_change > /dev/null && skip "分级库存刷新占用同一 Chrome"
```

- [ ] **Step 2: plist StartCalendarInterval 改数组（PlistBuddy，绝不裸 plutil -extract）**

```bash
F=~/Library/LaunchAgents/com.spzx.stock-sync.plist
plutil -extract StartCalendarInterval -o - "$F"     # 读（带 -o - 才安全）
/usr/libexec/PlistBuddy -c "Delete :StartCalendarInterval" "$F"
/usr/libexec/PlistBuddy -c "Add :StartCalendarInterval array" "$F"
/usr/libexec/PlistBuddy -c "Add :StartCalendarInterval:0 dict -c 'Add :Hour integer 5' -c 'Add :Minute integer 30'" "$F"
/usr/libexec/PlistBuddy -c "Add :StartCalendarInterval:1 dict -c 'Add :Hour integer 12' -c 'Add :Minute integer 30'" "$F"
/usr/libexec/PlistBuddy -c "Add :StartCalendarInterval:2 dict -c 'Add :Hour integer 19' -c 'Add :Minute integer 30'" "$F"
plutil -lint "$F"
launchctl bootout gui/$(id -u)/com.spzx.stock-sync 2>/dev/null
launchctl bootstrap gui/$(id -u) "$F"
launchctl print gui/$(id -u)/com.spzx.stock-sync | grep -A12 StartCalendarInterval   # 必须回 3 组时刻
cp "$F" scripts/launchd/com.spzx.stock-sync.plist && cmp "$F" scripts/launchd/com.spzx.stock-sync.plist && echo COPY_OK
```
plist 头部注释同步补「2026-10-18 起一日三跑 05:30/12:30/19:30」。

- [ ] **Step 3: 注册表口径**

`ingest_dataset.isv_stock_sync.cron_expr` 保持 `30 5 * * *`（首跑时刻）；如该表有 remark/备注类列（先 `SHOW COLUMNS FROM ingest_dataset;` 确认）补一句「一日三跑 05:30/12:30/19:30，同作业多触发」。check-consistency 若对多时刻报漂移：按「同脚本多 plist 时刻取并集」调整该检查后跑到绿。

- [ ] **Step 4: 验证**

```bash
python3 scripts/check-consistency.py
curl -s -m5 127.0.0.1:9222/json/version >/dev/null && cd automation/sourcing && $PY isv_stock_sync.py --pages 1 --dry-run   # 白天跑守卫应放行(dry 不写)
```

---

### Task 13: 收尾（一致性 + 文档 + 留痕）

- [ ] **Step 1: 全量验证**

```bash
cd automation/sourcing && $PY test_offer_fetch.py && $PY test_backfill_offer_archive.py && $PY test_tiered_selection.py && $PY test_detect_source_dead.py && $PY test_isv_sync_verify.py
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn test -pl spzx-manager -am -Dtest=LowStockParamTest -Dsurefire.failIfNoSpecifiedTests=false
python3 scripts/check-consistency.py
```
Expected: 全绿、0 fail。

- [ ] **Step 2: AGENTS.md 更新**

- `automation/sourcing/AGENTS.md`：新增三节——「货源全量建档 backfill_offer_archive」（映射即进度/避开周六/风控节奏）、「分级刷新 --tiered」（T1/T2/T3 口径、硬停钟 05:00、与 ISV 同步互斥守卫）、「ISV 同步核验 isv_sync_verify」（探针结论、verdict 口径、stock_sync_check 表）；调度速查里 05:00 行改注「仅告警检测，采集已迁 03:00」。
- 根 `AGENTS.md` ingest 节补一行 `source_dead` 告警类型与销案路径（复活自动销案）。

- [ ] **Step 3: spec/进度回填 + log_work**

- `docs/superpowers/specs/2026-10-18-source-stock-monitor-design.md` 尾部追加实施结果小节（各期实际数字：补映射 N 行、建档 N、dead N、探针结论、核验通过率）。
- `python3 scripts/log_work.py --module 其它 --title "1688货源库存监控闭环(P1-P4)" --progress "..." --merge`。
- **不 commit**——全部改动留给 owner 审后自行提交。
