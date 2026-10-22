# 在售口径收敛 M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 三个 Chrome 定时任务收敛到「在售 889」口径：新增 sync_onsale 每日扫描落 `onsale_snapshot`，库存同步只翻 9 页，推广日报挪 12:06（D-1 口径已天然满足），补 chrome-kill 收尾作业，四份副本对齐。

**Architecture:** 控制台「商品状态: 销售中」是前端过滤、行内带货源状态/库存（2026-10-19 中午探针实测）→ 一次 9 页 DOM 扫描同时产出在售清单与货源库存快照；库存同步复用同一筛选把 39 页压到 9 页；分级刷新 M2（另期）切抽查模式。

**Tech Stack:** Python 3.9 (automation/venv) + Playwright async via CDP 9222 + MySQL(db_spzx) + launchd。

## Global Constraints

- **绝不 `git commit`/`git add`**（本仓库红线，覆盖技能模板里的 Commit 步骤——每任务以「验证/留痕」步骤收尾）
- Python 一律 `/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python`；单测直接 venv python 跑（无 pytest 依赖，用 unittest）
- MySQL 命令：`/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx`；cnf 缺失先 `python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/mysql-cnf.py`
- Chrome 9222：窗口模式静默（`--window-position=-32000,-32000` + `cdp_minimize.py`），**绝不 headless**；脚本**绝不调 `b.close()`**（0 标签病：connect 会报 Browser context management is not supported）；退出只关自己的 page
- 同一 9222 勿并行两任务：新增/修改的包装脚本必须有 pgrep 互斥守卫
- plist：读用 `PlistBuddy -c Print` 或 Read 工具；改用 Edit 工具直接编辑 XML（`plutil -extract` 不带 `-o -` 会原地覆写文件，勿用）；改后 `plutil -lint` + `launchctl bootout/bootstrap` + `launchctl print` 复核；仓库副本 `scripts/launchd/` 与 `~/Library/LaunchAgents/` 逐个 `cmp`
- 收尾必跑 `python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/check-consistency.py`（先 `--selftest`），退出码非 0 修到 0
- 9223/9224 与日常 Chrome 红线照旧（本计划不碰）

---

### Task 1: `onsale_snapshot` 表

**Files:**
- Create: `spzx-manager/src/main/resources/sql/onsale_snapshot.sql`

**Interfaces:**
- Produces: 表 `onsale_snapshot(snapshot_date, taobao_item_id, source_product_id, shop_status, source_status, source_price, source_stock, raw)`，唯一键 `(snapshot_date, taobao_item_id)`——Task 3 的 upsert 目标

- [ ] **Step 1: 写 DDL**

```sql
-- onsale_snapshot: 铺货平台「销售中」商品每日快照 (sync_onsale.py, spec 2026-10-19 onsale-refactor §3.1)
CREATE TABLE IF NOT EXISTS onsale_snapshot (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  snapshot_date DATE NOT NULL,
  taobao_item_id BIGINT NOT NULL,
  source_product_id BIGINT NULL,
  shop_status VARCHAR(20) NOT NULL DEFAULT '',
  source_status VARCHAR(20) NOT NULL DEFAULT '',
  source_price DECIMAL(10,2) NULL,
  source_stock INT NULL,
  raw VARCHAR(1024) NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_item (snapshot_date, taobao_item_id),
  KEY idx_date (snapshot_date),
  KEY idx_spi (source_product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='铺货平台在售商品每日快照';
```

- [ ] **Step 2: 建表并验证**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx < spzx-manager/src/main/resources/sql/onsale_snapshot.sql
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SHOW COLUMNS FROM onsale_snapshot;"
```
Expected: 11 列，含 `uk_date_item`。

### Task 2: sync_onsale 纯函数（TDD）

**Files:**
- Create: `automation/sourcing/sync_onsale.py`（本任务只建文件+纯函数骨架）
- Test: `automation/sourcing/test_sync_onsale.py`

**Interfaces:**
- Produces（Task 3 复用）:
  - `parse_row_text(txt: str) -> dict | None`（键 `taobao_item_id:int`, `source_status:str`, `source_price:float|None`, `source_stock:int|None`）
  - `parse_chip_counts(text: str) -> dict`（键=六个筛选名，值=int|None）
  - `pages_for(total: int, per_page: int = 100) -> int`
  - `diff_bindings(today_items: set, yesterday_items: set) -> tuple[set, set]`

- [ ] **Step 1: 写失败测试** `test_sync_onsale.py`

```python
import unittest
from sync_onsale import parse_row_text, parse_chip_counts, pages_for, diff_bindings

SAMPLE_ROW = ("预览\n2026新款豹纹整皮真兔毛皮草外套女中长款翻领立领风潮保暖\n"
              "ID：1073885580706\n复制\n同步记录\n销售中\nAI内容优化\n已匹配 1024元 48")
SAMPLE_CHIPS = ("快捷筛选：\n销售中(889)\n仓库中(2947)\n已关联货源(3831)\n未关联货源(1)\n"
                "关联货源已下架(222)\n价格倒挂(60)")

class TestParse(unittest.TestCase):
    def test_row_full(self):
        r = parse_row_text(SAMPLE_ROW)
        self.assertEqual(r["taobao_item_id"], 1073885580706)
        self.assertEqual(r["source_status"], "销售中")
        self.assertEqual(r["source_price"], 1024.0)
        self.assertEqual(r["source_stock"], 48)

    def test_row_no_item(self):
        self.assertIsNone(parse_row_text("无ID的行"))

    def test_row_without_triple(self):
        r = parse_row_text("ID：1093333948278\n其他")
        self.assertEqual(r["taobao_item_id"], 1093333948278)
        self.assertEqual(r["source_status"], "")
        self.assertIsNone(r["source_price"])

    def test_chips(self):
        c = parse_chip_counts(SAMPLE_CHIPS)
        self.assertEqual(c["销售中"], 889)
        self.assertEqual(c["仓库中"], 2947)
        self.assertEqual(c["价格倒挂"], 60)
        self.assertIsNone(c.get("不存在筛选"))

    def test_pages(self):
        self.assertEqual(pages_for(889), 9)
        self.assertEqual(pages_for(100), 1)
        self.assertEqual(pages_for(0), 0)

    def test_diff(self):
        new, gone = diff_bindings({1, 2, 3}, {2, 3, 4})
        self.assertEqual(new, {1})
        self.assertEqual(gone, {4})

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python test_sync_onsale.py
```
Expected: FAIL（ImportError: sync_onsale 无纯函数）

- [ ] **Step 3: 最小实现**（写进 `sync_onsale.py`，仅 import + 四个函数 + `if __name__` 骨架）

```python
ROW_ITEM_RE = re.compile(r"ID：?(\d{8,})")
ROW_TRIPLE_RE = re.compile(r"(销售中|仓库中|已下架)\s*([\d.]+)元\s*(\d+)")
CHIP_KEYS = ("销售中", "仓库中", "已关联货源", "未关联货源", "关联货源已下架", "价格倒挂")

def parse_row_text(txt):
    m = ROW_ITEM_RE.search(txt or "")
    if not m:
        return None
    row = {"taobao_item_id": int(m.group(1))}
    t = ROW_TRIPLE_RE.search(txt)
    if t:
        row["source_status"], row["source_price"], row["source_stock"] = t.group(1), float(t.group(2)), int(t.group(3))
    else:
        row["source_status"], row["source_price"], row["source_stock"] = "", None, None
    return row

def parse_chip_counts(text):
    out = {}
    for key in CHIP_KEYS:
        m = re.search(re.escape(key) + r"[（(]([\d,]+)", text or "")
        out[key] = int(m.group(1).replace(",", "")) if m else None
    return out

def pages_for(total, per_page=100):
    return max(1, -(-total // per_page)) if total else 0

def diff_bindings(today_items, yesterday_items):
    return set(today_items) - set(yesterday_items), set(yesterday_items) - set(today_items)
```

- [ ] **Step 4: 跑测试确认全绿**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python test_sync_onsale.py -v
```
Expected: 6 tests PASS

### Task 3: sync_onsale.py 主扫描器 + 包装脚本

**Files:**
- Modify: `automation/sourcing/sync_onsale.py`（在 Task 2 基础上加 JS 常量、扫描主流程、落库、告警）
- Create: `automation/sourcing/run_onsale_scan.sh`

**Interfaces:**
- Consumes: `cdp_utils.connect_cdp / new_page_quiet`、`scrape_isv_offer_taobao.{open_page, get_frame, nav_to_guanli}`、`isv_stock_sync.{goto_page, set_page_size}`（import 复用，勿复制）、`dbconf.DB_CONFIG`、Task 2 四个纯函数
- Produces: 每日 `onsale_snapshot` 当日行；`sync_alert`(type=`onsale_binding_change`)；stdout 行 `入库 N 条` 与 `销售中 N 个`（包装脚本 tail 切片取数）

- [ ] **Step 1: JS 常量与扫描主流程**（追加到 sync_onsale.py）

```python
import asyncio, sys, time
sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from cdp_utils import connect_cdp, minimize_windows
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli
import isv_stock_sync as S  # 复用 goto_page / set_page_size / body_text

JS_FILTER = """() => {
  const els = [...document.querySelectorAll('span,div,button,a,li')];
  for (const e of els) {
    const t = (e.textContent||'').replace(/\\s+/g,'');
    if ((t === '商品状态:销售中' || t === '销售中') && e.children.length<=2) { e.click(); return t; }
  }
  return null;
}"""
JS_ROWS = """() => {
  const out = [];
  for (const tr of document.querySelectorAll('tr')) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 5) continue;
    const txt = (tr.innerText||'');
    if (!/ID：?\\d{8,}/.test(txt)) continue;
    out.push(txt.replace(/\\t/g,' ').slice(0, 600));
  }
  return out;
}"""

def log(m): print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)

def upsert_rows(date_str, rows):
    from dbconf import DB_CONFIG
    import pymysql
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4')
    cur = conn.cursor()
    sql = ("INSERT INTO onsale_snapshot (snapshot_date, taobao_item_id, source_product_id, "
           "shop_status, source_status, source_price, source_stock, raw) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
           "ON DUPLICATE KEY UPDATE source_product_id=VALUES(source_product_id), shop_status=VALUES(shop_status), "
           "source_status=VALUES(source_status), source_price=VALUES(source_price), source_stock=VALUES(source_stock), raw=VALUES(raw)")
    cur.executemany(sql, [(date_str, r["taobao_item_id"], r.get("source_product_id"), "销售中",
                           r.get("source_status"), r.get("source_price"), r.get("source_stock"),
                           r.get("raw")) for r in rows])
    conn.commit(); cur.close(); conn.close()
    return len(rows)

def yesterday_items(date_str):
    from dbconf import DB_CONFIG
    import pymysql
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4')
    cur = conn.cursor()
    cur.execute("SELECT taobao_item_id FROM onsale_snapshot WHERE snapshot_date = DATE_SUB(%s, INTERVAL 1 DAY)", (date_str,))
    rows = {int(r[0]) for r in cur.fetchall()}
    cur.close(); conn.close()
    return rows

def write_stock_alerts(rows_map, low_threshold=10):
    """超卖风险/低库存告警（spec §3.6，按天去重）。rows_map: item_id → row"""
    from dbconf import DB_CONFIG
    import pymysql
    oversell = [r for r in rows_map.values()
                if r.get("source_status") == "已下架" or r.get("source_stock") == 0]
    low = [r for r in rows_map.values()
           if r.get("source_stock") is not None and 0 < r["source_stock"] <= low_threshold]
    if not oversell and not low:
        return 0
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4')
    cur = conn.cursor()
    n = 0
    for atype, items, msg in (
            ("oversell_risk", oversell,
             f"超卖风险: {len(oversell)} 个在售商品货源已下架/0库存 (含ID {','.join(str(r['taobao_item_id']) for r in oversell[:5])}...)"),
            ("low_stock", low,
             f"低库存: {len(low)} 个在售商品货源库存≤{low_threshold} (含ID {','.join(str(r['taobao_item_id']) for r in low[:5])}...)")):
        if not items:
            continue
        cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type=%s AND status=0 AND DATE(create_time)=%s",
                    (atype, time.strftime('%Y-%m-%d')))
        if cur.fetchone()[0]:
            continue
        cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES (%s,%s,0,NOW())",
                    (atype, msg))
        n += 1
    conn.commit(); cur.close(); conn.close()
    return n
```

绑定对账告警（第 4 个纯函数）：

```python
def write_binding_alerts(new_ids, gone_ids, date_str):
    """按天去重写 sync_alert（与 detect_alerts.detect_source_dead 同一去重口径，先 SELECT 再 INSERT）"""
    from dbconf import DB_CONFIG
    import pymysql
    if not new_ids and not gone_ids:
        return 0
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4')
    cur = conn.cursor()
    n = 0
    for kind, ids, msg in (("新增", new_ids, f"在售清单新增 {len(new_ids)} 个商品"),
                           ("消失", gone_ids, f"在售清单消失 {len(gone_ids)} 个商品（下架/删除，若在售则超卖风险）")):
        if not ids:
            continue
        cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type='onsale_binding_change' AND status=0 "
                    "AND message LIKE %s AND DATE(create_time)=%s", (f"%在售清单{kind}%", date_str))
        if cur.fetchone()[0]:
            continue
        cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES (%s,%s,0,NOW())",
                    ("onsale_binding_change", msg))
        n += 1
    conn.commit(); cur.close(); conn.close()
    return n
```

主流程（async main）：

```python
async def scan(args):
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com"], log=log)
    page = None
    rows_map = {}
    try:
        page = await open_page(ctx, quiet=True)
        fr = await get_frame(page)
        if not fr or not await fr.locator(".ant-table-row").first.count():
            await nav_to_guanli(fr)
        await fr.evaluate(JS_FILTER)
        await asyncio.sleep(4)
        body = await S.body_text(fr)
        chips = parse_chip_counts(body)
        total = chips["销售中"]
        if not total:
            log("!! 销售中计数为 0（筛选没生效/登录态掉了）")
            return 2
        log(f"销售中 {total} 个 → {pages_for(total)} 页")
        if not await S.set_page_size(fr):
            await asyncio.sleep(5)
            if not await S.set_page_size(fr):
                return 3
        pages = pages_for(total)
        if args.pages:
            pages = min(pages, args.pages)
        for pg in range(1, pages + 1):
            if pg > 1 and not await S.goto_page(fr, pg):
                log(f"!! 第 {pg} 页跳转失败, 用已得数据继续")
                break
            await asyncio.sleep(2)
            for txt in await fr.evaluate(JS_ROWS):
                r = parse_row_text(txt)
                if r:
                    r["raw"] = txt[:1000]
                    rows_map[r["taobao_item_id"]] = r
            log(f"page {pg}: 累计 {len(rows_map)}")
        # source_product_id 反查（taobao_offer_map: taobao_item_id → source_product_id）
        from dbconf import DB_CONFIG
        import pymysql
        conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4'); cur = conn.cursor()
        for iid, r in rows_map.items():
            cur.execute("SELECT source_product_id FROM taobao_offer_map WHERE taobao_item_id=%s LIMIT 1", (iid,))
            hit = cur.fetchone()
            r["source_product_id"] = int(hit[0]) if hit and hit[0] is not None else None
        cur.close(); conn.close()
        date_str = time.strftime('%Y-%m-%d')
        log(f"样本: {list(rows_map.values())[0] if rows_map else '无'}")
        if args.dry_run:
            log(f"[dry-run] 共 {len(rows_map)} 行, 未落库")
            return 0
        n = upsert_rows(date_str, list(rows_map.values()))
        log(f"入库 {n} 条")
        old = yesterday_items(date_str)
        new_ids, gone_ids = diff_bindings(set(rows_map), old)
        alerts = write_binding_alerts(new_ids, gone_ids, date_str)
        n_stock = write_stock_alerts(rows_map)
        log(f"对账: 新增 {len(new_ids)} 消失 {len(gone_ids)}, 绑定告警 {alerts}, 超卖/低库存告警 {n_stock}")
        return 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass
        # 绝不 b.close()；守卫 tab 由包装脚本 ensure_chrome 兜底

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pages", type=int, default=0)
    args = ap.parse_args()
    sys.exit(asyncio.run(scan(args)))
```

- [ ] **Step 2: 包装脚本** `run_onsale_scan.sh`（chmod +x）

```bash
#!/bin/bash
# 每日 12:40 铺货平台在售扫描 (LaunchAgent com.spzx.onsale-scan, spec onsale-refactor §3.1)
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/onsale_scan.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=onsale_scan

skip() {
  echo "[$(date '+%m-%d %H:%M')] $1, 跳过" >> "$LOG"
  $PY "$ALERT" --key onsale_scan --dataset "$DS" --platform 1 --msg "在售扫描未跑: $1" > /dev/null 2>&1
  local bid; bid=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
pgrep -f "isv_stock_sync|detect_stock_change|collect_alimama|sycm_item_snapshot" >/dev/null && skip "9222 上有其他采集任务"
pgrep -f "sync_onsale" >/dev/null && skip "上一轮未结束"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 在售扫描 开始 ===" >> "$LOG"
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
BID=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
$PY sync_onsale.py "$@" >> "$LOG" 2>&1
rc=$?
ROWS=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | sed -n "s/.*入库 \([0-9]*\) 条.*/\1/p" | tail -1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 在售扫描 结束 rc=$rc rows=${ROWS:-0} ===" >> "$LOG"
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "sync_onsale 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key onsale_scan --dataset "$DS" --platform 1 --type cron_failed --msg "在售扫描异常退出 rc=$rc" > /dev/null 2>&1
fi
ensure_chrome   # 退出兜底: 0 标签病态补守卫 tab
exit $rc
```

- [ ] **Step 3: 语法验证**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python -m py_compile sync_onsale.py && bash -n run_onsale_scan.sh && echo OK
```
Expected: OK。真实扫描首跑放 Task 8（明天中午窗口，先 --dry-run）。

### Task 4: 注册表 + 看板卡片登记 onsale_scan

**Files:**
- Modify: `automation/sourcing/task-progress-config.json`（tasks 数组加一条）
- DB: `ingest_dataset` 两行

**Interfaces:**
- Produces: dataset `onsale_scan`（cron `40 12 * * *`, monitor=1）；`promo_cost` cron 改 `6 12 * * *`——Task 8 一致性门的输入

- [ ] **Step 1: 注册表 SQL**（保存到 `/tmp/onsale_registry.sql` 再执行）

```sql
INSERT INTO ingest_dataset (code, name, platform_code, measure, target_table, freshness_col,
  natural_key_cols, required_cols, sla_hours, monitor, writer, cron_expr, remark)
VALUES ('onsale_scan','铺货平台在售扫描',1,'table','onsale_snapshot','update_time',
  'snapshot_date,taobao_item_id','taobao_item_id',24,1,'sync_onsale.py','40 12 * * *',
  '2026-10-19 onsale-refactor: 中午静默窗口扫描销售中(889), 快照+绑定对账')
ON DUPLICATE KEY UPDATE cron_expr='40 12 * * *', monitor=1, writer='sync_onsale.py';
UPDATE ingest_dataset SET cron_expr='6 12 * * *' WHERE code='promo_cost';
```

执行后验证：`SELECT code, cron_expr, monitor FROM ingest_dataset WHERE code IN ('onsale_scan','promo_cost');`

- [ ] **Step 2: 卡片登记**（Read `task-progress-config.json` → 照抄 freight_fetch 条目字段结构，改值插入）

```json
{"key": "onsale_scan", "name": "铺货平台在售扫描", "category": "scheduled",
 "tags": ["在售", "定时·每日12:40"], "port": 9222, "type": "list_progress",
 "path": "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/onsale_snapshot_progress.json",
 "script": "run_onsale_scan.sh", "logPath": "/tmp/onsale_scan.log",
 "schedule": "每日 12:40", "dataset": "onsale_scan",
 "launchCmd": "cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ./run_onsale_scan.sh"}
```
（字段以 freight_fetch 实际结构为准，缺的字段不硬造；`onsale_snapshot_progress.json` 由 sync_onsale 每轮写 `{date, total, rows}`。）

- [ ] **Step 3: 验证 JSON**

```bash
python3 -c "import json; json.load(open('/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/task-progress-config.json')); print('JSON OK')"
```

### Task 5: isv_stock_sync 在售化

**Files:**
- Modify: `automation/sourcing/isv_stock_sync.py:225-231`（已关联货源 chip 之后插筛选与计数）、argparse 加 `--scope`
- Modify: `automation/sourcing/run_stock_sync.sh`（守卫补 collect_alimama）

**Interfaces:**
- Consumes: 同款 `JS_FILTER` 文本（与 sync_onsale.py 逐字一致——一致性门检查 D 钉 cron_alert，这里靠自测）
- Produces: 默认 `--scope onsale`，total=销售中计数；`--scope all` 保留旧行为

- [ ] **Step 1: argparse 加 scope**（isv_stock_sync.py main 里）

```python
ap.add_argument("--scope", choices=("onsale", "all"), default="onsale",
                help="onsale=只处理销售中(默认, 9页); all=全部已关联货源(旧行为)")
```

- [ ] **Step 2: run() 里已关联货源 chip 点击之后、set_page_size 之前插入**

```python
if args.scope == "onsale":
    clicked = await fr.evaluate("""() => {
      const els = [...document.querySelectorAll('span,div,button,a,li')];
      for (const e of els) {
        const t = (e.textContent||'').replace(/\\s+/g,'');
        if ((t === '商品状态:销售中' || t === '销售中') && e.children.length<=2) { e.click(); return t; }
      }
      return null; }""")
    await asyncio.sleep(4)
    body = await body_text(fr)
    m = re.search(r'销售中[（(]([\d,]+)', body)
    total = int(m.group(1).replace(',', '')) if m else 0
    log(f"在售口径: 销售中 {total} 个 (筛选点击: {clicked})")
    if not total:
        log("!! 销售中计数为 0, 放弃本轮")
        return 4
```

- [ ] **Step 3: run_stock_sync.sh 守卫补一行**（与 cron_alimama_promo 互避，12:06 vs 12:30）

```bash
# 守卫: 推广日报采集中(同Chrome勿并行) → 跳过
pgrep -f collect_alimama_promo > /dev/null && skip "推广日报采集占用同一 Chrome"
```

- [ ] **Step 4: 语法验证 + dry-run 意义上的静态确认**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python -m py_compile isv_stock_sync.py && bash -n run_stock_sync.sh && echo OK
```

### Task 6: 推广日报挪 12:06 + 互避守卫

**Files:**
- Modify: `~/Library/LaunchAgents/com.spzx.alimama-promo.plist` 与 `scripts/launchd/com.spzx.alimama-promo.plist`（Hour 22→12, Minute 0→6）
- Modify: `automation/tb-auto/cron_alimama_promo.sh:40`（守卫清单补 `|isv_stock_sync|sync_onsale`）
- Modify: `~/docs/cron.md`

**Interfaces:**
- Consumes: 采集脚本 `--to` 默认昨天（collect_alimama_promo.py:866 **已天然满足 D-1 口径，零代码改动**——spec 此节假设已由计划期核实修正）
- Produces: launchd 每日 12:06 触发

- [ ] **Step 1: 编辑两份 plist**（Read 后 Edit：`<integer>22</integer>` → `<integer>12</integer>`，`<integer>0</integer>`（Minute）→ `<integer>6</integer>`；只动 StartCalendarInterval 内的键）

- [ ] **Step 2: lint + 重载 + 复核**

```bash
plutil -lint ~/Library/LaunchAgents/com.spzx.alimama-promo.plist scripts/launchd/com.spzx.alimama-promo.plist
cmp ~/Library/LaunchAgents/com.spzx.alimama-promo.plist /Users/qyk9527/ideaProject/spzx-parent/scripts/launchd/com.spzx.alimama-promo.plist && echo "副本一致"
launchctl bootout gui/$(id -u)/com.spzx.alimama-promo 2>/dev/null; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.alimama-promo.plist
launchctl print gui/$(id -u)/com.spzx.alimama-promo | grep -A4 StartCalendarInterval
```
Expected: 两键 12/6。

- [ ] **Step 3: cron_alimama_promo.sh 守卫清单追加**

```bash
pgrep -f "sycm_item_snapshot|assign_shop_category|collect_1688_full|collect_in_stock_current|detect_stock|auto_list|edit_isv_drafts|cron_collect_full|isv_sku_match|isv_stock_sync|sync_onsale" > /dev/null \
  && skip "9222 上有其他采集任务在跑"
```

- [ ] **Step 4: `~/docs/cron.md` 更新**（把 alimama 行改成 12:06 + 注明 D-1 口径本来就满足 + onsale_scan 12:40 新行 + chrome-kill 13:57/05:10）

### Task 7: chrome-kill 收尾作业

**Files:**
- Create: `automation/sourcing/chrome_kill.sh`（chmod +x）
- Create: `scripts/launchd/com.spzx.chrome-kill.plist` + 拷贝到 `~/Library/LaunchAgents/`

**Interfaces:**
- Consumes: pgrep 任务名清单（与 Task 3/5/6 的守卫同名）
- Produces: 每日 13:57 / 05:10 收 9222（有任务在跑则放过并留日志）

- [ ] **Step 1: `chrome_kill.sh`**

```bash
#!/bin/bash
# 窗口外收 9222 (13:57 / 05:10, spec onsale-refactor §3.5)。有任务在跑 → 放过并留日志。
LOG=/tmp/chrome_kill.log
BUSY="isv_stock_sync|detect_stock_change|collect_alimama|sycm_item_snapshot|sync_onsale|isv_sku_match|assign_shop_category_v2|edit_brand_title_batch|backfill_offer_archive|probe_"
if pgrep -f "$BUSY" >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] 任务在跑, 保留 Chrome" >> "$LOG"
  exit 0
fi
if pkill -f "remote-debugging-port=9222"; then
  echo "[$(date '+%F %T')] 已收 9222" >> "$LOG"
else
  echo "[$(date '+%F %T')] 本来就不在线" >> "$LOG"
fi
```

- [ ] **Step 2: plist（直接写 XML，两段 StartCalendarInterval）**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spzx.chrome-kill</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/chrome_kill.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>13</integer>
            <key>Minute</key>
            <integer>57</integer>
        </dict>
        <dict>
            <key>Hour</key>
            <integer>5</integer>
            <key>Minute</key>
            <integer>10</integer>
        </dict>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/chrome_kill_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/chrome_kill_launchd.log</string>
</dict>
</plist>
```

- [ ] **Step 3: 安装 + 验证 + 试跑**

```bash
plutil -lint scripts/launchd/com.spzx.chrome-kill.plist
cp scripts/launchd/com.spzx.chrome-kill.plist ~/Library/LaunchAgents/com.spzx.chrome-kill.plist
launchctl bootout gui/$(id -u)/com.spzx.chrome-kill 2>/dev/null; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.chrome-kill.plist
launchctl print gui/$(id -u)/com.spzx.chrome-kill | grep -B1 -A3 "integer"
launchctl kickstart gui/$(id -u)/com.spzx.chrome-kill; sleep 2; tail -2 /tmp/chrome_kill.log
```
Expected: print 显示 13:57 与 05:10 两段；试跑日志「本来就不在线」。

### Task 8: 一致性门 + 真跑排期 + 留痕

**Files:** 无新文件；运行验证

- [ ] **Step 1: 一致性门**

```bash
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/check-consistency.py --selftest && python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/check-consistency.py
```
Expected: selftest 报得出红；正式跑 0 fail。红灯按输出修（常见：卡片缺 schedule、注册表 cron_expr 与 plist 时刻不一致）。

- [ ] **Step 2: 真跑排期（明天中午窗口）**

12:03 ensure_chrome 自启（Task 3 包装）→ 12:06 alimama（新时刻首跑，验证 D-1 落库）→ 12:30 sync（9 页在售）→ 12:40 `run_onsale_scan.sh --dry-run`（owner 看样本数据）→ 放开全量 → 13:57 chrome-kill。产物核对：`onsale_snapshot` 当日行数≈889、`ingest_batch` onsale_scan success、`/tmp/alimama_promo_cron.log` 12:06 开始、`/tmp/chrome_kill.log` 13:57 收 9222。

- [ ] **Step 3: 留痕**

```bash
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/log_work.py --module 系统 \
  --title "在售口径M1落地(sync_onsale/库存同步9页/alimama挪12:06/chrome-kill)" --merge
```
