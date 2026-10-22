#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isv_sku_match.py — 分销控制台「规格匹配」全量过一遍（9222）。

背景：淘宝商品库存同步走 1688 淘分销，同步是 SKU 规格级 —— 淘宝商品每个 SKU 规格必须与
1688 货源 SKU 1:1 匹配，否则同步对不上。控制台「商品管理」操作列「更多」→「匹配规格」抽屉
自带「自动匹配规格」按钮。

流程（用户定稿 2026-10-14）：「已关联货源」**每个商品都过一遍**（已匹配的也不例外）：
  开抽屉 → 读规格表 → 计数/重复/未匹配检查 → 点「自动匹配规格」→ 回读 → 点「确 认」保存。
  自动匹配后仍未匹配的 → 记 manual_needed 人工处理；
  淘宝 SKU 数 ≠ 1688 规格数 → 记 count_mismatch；
  同一 1688 规格被绑到多个淘宝 SKU → 记 sku_duplicate（违反 1:1，不自动改）。

1688 规格数来源（两级）：
  ① DB source_sku（collect_1688_full 采的 sku_key，按 source_product_url 含 offer/<id>.html 关联，
     精确，spec_source=db）；
  ② DB 没有 → 读抽屉规格选择器(.spec-select-dropdown)的 radio 组数求积（估算，spec_source=picker_est，
     选择器是「颜色/尺码」维度 radio + 取消/确认，非普通下拉，读不到 option 列表）；
  ③ 再取不到 → offer_count=None，不判 count_mismatch（spec_source=none）。

默认 --dry-run（只读+记录+「取 消」关抽屉）；--apply 才真正点「自动匹配规格」+「确 认」。
报告 json 是唯一状态，按 item_id 续跑；终态(ok/manual_needed/count_mismatch/sku_duplicate)跳过。

坑（实测）：抽屉 fixed 定位可见性用 .ant-drawer-open（勿用 offsetParent）；**关抽屉绝不用键盘
Escape**（键盘事件发到外层页面，iframe 里的抽屉收不到，会一直开着挡住后续一切点击）——只走
抽屉内「取消」按钮 / .ant-drawer-close / .ant-drawer-mask。快捷筛选 chip 文本带计数后缀
（已关联货源(4183)），要前缀匹配不能全等。

跑法：
  automation/venv/bin/python isv_sku_match.py --limit 2 --dry-run          # 预演
  automation/venv/bin/python isv_sku_match.py --limit 1 --apply            # 试点(用户盯)
  nohup automation/venv/bin/python -u isv_sku_match.py --apply --gap 10 > /tmp/sku_match_run.log 2>&1 &
前置：9222 已登录分销控制台（窗口模式）。
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_utils import connect_cdp  # noqa: E402
from scrape_isv_offer_taobao import (  # noqa: E402
    get_frame, open_page, nav_to_guanli, click_page, click_next, read_total, ROWS_JS,
)
from dbconf import DB_CONFIG  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(BASE, "sku_match_report.json")
DEFAULT_CSV = os.path.join(BASE, "sku_match_manual.csv")
FINAL = {"ok", "manual_needed", "count_mismatch", "sku_duplicate", "offer_delisted", "open_fail"}


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


# ---------------- DB：offer → 1688 规格清单 ----------------

_SPEC_CACHE = {}


def offer_specs_from_db(offer_id):
    """source_product_url 含 offer/<id>.html → source_sku.sku_key 清单。没有返回 None。"""
    if offer_id in _SPEC_CACHE:
        return _SPEC_CACHE[offer_id]
    out = None
    try:
        import pymysql
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT ss.sku_key FROM source_product sp "
            "JOIN source_sku ss ON ss.source_product_id = sp.id "
            "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE %s "
            "AND ss.is_deleted=0 AND ss.status=1", (f"%offer/{offer_id}.html%",))
        out = [r[0] for r in cur.fetchall()] or None
        cur.close()
        conn.close()
    except Exception as e:
        log(f"   !! DB 查询失败 offer={offer_id}: {str(e)[:70]}")
    _SPEC_CACHE[offer_id] = out
    return out


# ---------------- 纯函数（可单测） ----------------

def parse_spec_name(cell):
    """'预览 2XL 灰色 价格：36.39元 库存：10000' -> '2XL 灰色'。"""
    m = re.search(r"预览\s+(.*?)\s*价格：", cell or "")
    return m.group(1).strip() if m else ""


def parse_price_stock(cell):
    p = re.search(r"价格：([\d.]+)元", cell or "")
    s = re.search(r"库存：([\d,]+)", cell or "")
    return (p.group(1) if p else None, s.group(1).replace(",", "") if s else None)


def analyze_rows(rows, offer_specs=None, offer_count=None):
    """rows=[{name,status,bound}]（name 为空的行跳过）。
    offer_specs=1688 规格名清单（精确，spec_source=db）；或 None 时用 offer_count（估算）；
    两者都缺 → count_mismatch=None（不判）。
    返回 {taobao_count, offer_count, unmatched, duplicates, count_mismatch}。"""
    names = [r["name"] for r in rows if r.get("name")]
    unmatched = [r["name"] for r in rows
                 if r.get("name") and (r.get("status") or "").strip() != "已匹配"]
    seen = {}
    for r in rows:
        bnd = (r.get("bound") or "").strip()
        if bnd:
            seen[bnd] = seen.get(bnd, 0) + 1
    dup = sorted(k for k, v in seen.items() if v > 1)
    if offer_specs is not None:
        cnt = len(offer_specs)
    elif offer_count is not None:
        cnt = offer_count
    else:
        return {"taobao_count": len(names), "offer_count": None,
                "unmatched": unmatched, "duplicates": dup, "count_mismatch": None}
    return {"taobao_count": len(names), "offer_count": cnt,
            "unmatched": unmatched, "duplicates": dup,
            "count_mismatch": len(names) != cnt}


def upsert(rep, item_id, item):
    for i, old in enumerate(rep["items"]):
        if old.get("item_id") == item_id:
            rep["items"][i] = item
            return
    rep["items"].append(item)


def manual_csv_rows(rep):
    """人工处理清单。manual_needed 每个未匹配规格一行（若同时 count_mismatch 再补一行）；
    count_mismatch / sku_duplicate 各一行（明细 json）。"""
    out = []
    for it in rep["items"]:
        st = it.get("status")
        iid, title = it.get("item_id", ""), it.get("title", "")
        if st == "manual_needed":
            for name in it.get("unmatched", []):
                out.append([iid, title, "manual_needed", name])
            if it.get("count_mismatch"):
                out.append([iid, title, "count_mismatch",
                            f"淘宝{it.get('taobao_sku_count')} vs 1688{it.get('offer_spec_count')}({it.get('spec_source')})"])
        elif st in ("count_mismatch", "sku_duplicate"):
            out.append([iid, title, st,
                        json.dumps({k: v for k, v in it.items()
                                    if k in ("taobao_sku_count", "offer_spec_count",
                                             "spec_source", "duplicates", "unmatched",
                                             "offer_dims")}, ensure_ascii=False)])
        elif st == "open_fail":
            out.append([iid, title, "open_fail", it.get("note", "")])
    return out


def write_csv(path, rep):
    rows = manual_csv_rows(rep)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "title", "type", "detail"])
        w.writerows(rows)
    return len(rows)


# ---------------- 报告 IO ----------------

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


def title_from_row_text(text):
    t = (text or "").split(" ID：")[0]
    return re.sub(r"^预览\s*", "", t).strip()[:60]


# ---------------- 抽屉操作（探针实测选择器） ----------------

READ_DRAWER_ROWS_JS = r"""() => {
  const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const ds = [...document.querySelectorAll('.ant-drawer-open')];
  if (!ds.length) return null;
  const d = ds.sort((a, b) => (b.innerText || '').length - (a.innerText || '').length)[0];
  const out = [];
  for (const tr of d.querySelectorAll('tbody tr')) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 2) continue;
    const sel = tr.querySelector('.ant-select-selection-item, .next-select-selection-item');
    out.push({ cell0: t(tds[0]), status: tds[1] ? t(tds[1]) : '',
               bound: sel ? t(sel) : '' });
  }
  return out;
}"""

READ_PICKER_JS = r"""() => {
  const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const pks = [...document.querySelectorAll('.spec-select-dropdown')]
    .filter(e => e.getClientRects().length > 0);
  if (!pks.length) return null;
  const p = pks[0];
  const groups = [];
  for (const fi of p.querySelectorAll('.ant-form-item')) {
    const label = fi.querySelector('.spec-name');
    if (!label) continue;
    const opts = [...fi.querySelectorAll('.ant-radio-button-wrapper')]
      .map(e => t(e)).filter(x => x);
    if (opts.length) groups.push({ dim: t(label), opts });
  }
  return groups.length ? groups : null;
}"""


ROW_MATCH_STATUS_JS = r"""(id) => {
  const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  const tr = [...document.querySelectorAll('.ant-table-row')]
    .find(r => (r.innerText || '').includes('ID：' + id));
  if (!tr) return null;
  const tds = tr.querySelectorAll('td');      // 列: 2商品信息 3商品状态 4规格匹配状态 ...
  return tds[4] ? t(tds[4]) : null;
}"""


async def row_match_status(fr, item_id):
    try:
        return await fr.evaluate(ROW_MATCH_STATUS_JS, item_id)
    except Exception:
        return None


async def drawer_open(fr):
    """抽屉真实可见（.ant-drawer-open 且 content 有渲染框；关抽屉动画期间类名还在）。"""
    return await fr.evaluate(r"""() => {
      for (const d of document.querySelectorAll('.ant-drawer-open')) {
        const c = d.querySelector('.ant-drawer-content');
        if (c && c.getClientRects().length > 0) return true;
      }
      return false;
    }""")


async def click_drawer_btn(fr, label):
    """抽屉内按钮，按「去空格后全等」匹配。JS 打标记后定位点击（过滤不可见按钮）。"""
    got = await fr.evaluate(r"""(lab) => {
      const vis = e => e.getClientRects().length > 0;
      for (const d of document.querySelectorAll('.ant-drawer-open')) {
        if (!vis(d.querySelector('.ant-drawer-content') || d)) continue;
        for (const b of d.querySelectorAll('button')) {
          b.removeAttribute('data-skm');
          if (vis(b) && !b.disabled &&
              (b.innerText || '').replace(/\s+/g, '') === lab) b.setAttribute('data-skm', '1');
        }
      }
      return !!document.querySelector('.ant-drawer-open button[data-skm="1"]');
    }""", label)
    if not got:
        return False
    loc = fr.locator('.ant-drawer-open button[data-skm="1"]').first
    try:
        await loc.click(timeout=4000)
        return True
    except Exception:
        try:
            await loc.click(timeout=3000, force=True)
            return True
        except Exception as e:
            log(f"   !! 点按钮 {label} 失败: {str(e)[:70]}")
            return False
    finally:
        await fr.evaluate("""() => {
          for (const b of document.querySelectorAll('button[data-skm]')) b.removeAttribute('data-skm');
        }""")


async def ensure_drawer_closed(fr):
    """关抽屉：取消按钮 → 关闭X → 遮罩。绝不用键盘 Escape（事件到不了 iframe，抽屉关不掉）。"""
    for _ in range(3):
        if not await drawer_open(fr):
            return True
        await click_drawer_btn(fr, "取消")
        await asyncio.sleep(1.5)
        if not await drawer_open(fr):
            return True
        for sel in (".ant-drawer-open .ant-drawer-close", ".ant-drawer-open .ant-drawer-mask"):
            try:
                await fr.locator(sel).first.click(timeout=2000, force=True)
                await asyncio.sleep(1.5)
            except Exception:
                pass
    return not await drawer_open(fr)


async def open_match_drawer(fr, item_id):
    """对该 item 所在行开匹配规格抽屉。
    入口按行状态不同（实测）：「部分匹配」行操作列有**内联「匹配规格」按钮**（其「更多」菜单里
    反而没有该项）；「已匹配」行走 更多→匹配规格。返回 bool。"""
    await ensure_drawer_closed(fr)
    try:
        row = fr.locator(".ant-table-row", has_text=f"ID：{item_id}").first
        inline = row.locator("td").last.locator("text=匹配规格").first
        if await inline.count():
            await inline.click(timeout=6000)
        else:
            await row.locator("text=更多").first.click(timeout=6000)
            await asyncio.sleep(1.2)
            mi = fr.locator(".ant-dropdown:not(.ant-dropdown-hidden)").locator("text=匹配规格").first
            await mi.click(timeout=5000)
    except Exception as e:
        log(f"   !! 开抽屉失败: {str(e)[:80]}")
        return False
    for _ in range(12):
        await asyncio.sleep(1)
        if await drawer_open(fr):
            await asyncio.sleep(1.5)   # 等表格渲染
            return True
    return False


async def read_drawer_rows(fr):
    """读规格表全部行 → [{name, price, stock, status, bound}]；抽屉不在返回 None。"""
    raw = await fr.evaluate(READ_DRAWER_ROWS_JS)
    if raw is None:
        return None
    out = []
    for r in raw:
        name = parse_spec_name(r.get("cell0", ""))
        price, stock = parse_price_stock(r.get("cell0", ""))
        out.append({"name": name, "price": price, "stock": stock,
                    "status": r.get("status", ""), "bound": r.get("bound", "")})
    return out


async def read_picker_dims(fr):
    """点首行规格选择器(.ant-select-selector)打开 .spec-select-dropdown，
    读 radio 维度组，再用选择器自己的「取消」收起。返回 [{dim, opts}] 或 None。"""
    sel = fr.locator(".ant-drawer-open tbody tr").first.locator(".ant-select-selector").first
    try:
        if await sel.count() == 0:
            return None
        await sel.click(timeout=5000)
        groups = None
        for _ in range(8):
            await asyncio.sleep(0.5)
            groups = await fr.evaluate(READ_PICKER_JS)
            if groups:
                break
        # 收起：点选择器弹层里的「取消」（作用域限定在弹层内，勿点抽屉的取消）
        await fr.evaluate(r"""() => {
          const t=e=>(e.innerText||'').replace(/\s+/g,'').trim();
          const pks=[...document.querySelectorAll('.spec-select-dropdown')]
            .filter(e=>e.getClientRects().length>0);
          if(!pks.length) return;
          const b=[...pks[0].querySelectorAll('button')].find(x=>t(x.innerText||'')==='取消');
          if(b)b.click();
        }""")
        await asyncio.sleep(1)
        return groups
    except Exception as e:
        log(f"   !! 读规格选择器失败: {str(e)[:70]}")
        try:
            await fr.keyboard.press("Escape")   # 只为收弹层；抽屉若被误关下一轮 ensure 会兜住
        except Exception:
            pass
        return None


async def dismiss_confirm_dialog(fr):
    """「自动匹配规格」可能带确认弹层（ant-modal-confirm）→ 点确定。"""
    try:
        dlg = fr.locator(".ant-modal-confirm button", has_text="确").first
        if await dlg.count():
            await dlg.click(timeout=3000)
            await asyncio.sleep(1.5)
            return True
    except Exception:
        pass
    return False


# ---------------- 主流程 ----------------

async def process_row(fr, r, args, rep, report_path):
    """处理一行商品。返回 status 字符串。"""
    item_id = str(r.get("taobao_item_id") or "")
    offer_id = str(r.get("offer_id") or "")
    title = title_from_row_text(r.get("text", ""))

    def record_fail(note):
        """失败记档：同一商品第 2 次失败 → open_fail 终态（转人工，不再重试堵路）。"""
        prev = next((i for i in rep["items"] if i.get("item_id") == item_id), None)
        attempts = ((prev.get("attempts") or 0) + 1) \
            if prev and prev.get("status") == "drawer_fail" else 1
        status = "open_fail" if attempts >= 2 else "drawer_fail"
        it = {"item_id": item_id, "offer_id": offer_id, "title": title,
              "status": status, "note": note, "attempts": attempts,
              "ts": time.strftime("%F %T")}
        upsert(rep, item_id, it)
        save_report(report_path, rep)
        write_csv(args.csv, rep)
        return status

    if not await open_match_drawer(fr, item_id):
        return record_fail("open_fail")
    drows = await read_drawer_rows(fr)
    if drows is None:
        st = record_fail("drawer_lost")
        await ensure_drawer_closed(fr)
        return st

    # 1688 规格数：DB 精确 → 选择器估算 → None
    specs = offer_specs_from_db(offer_id) if offer_id else None
    dims = None
    if specs is not None:
        spec_source, offer_count = "db", len(specs)
    else:
        dims = await read_picker_dims(fr)
        if dims:
            est = 1
            for g in dims:
                est *= len(g["opts"])
            spec_source, offer_count = "picker_est", est
        else:
            spec_source, offer_count = "none", None
    before = analyze_rows(drows, specs, offer_count)

    def item_common(status, note=""):
        return {"item_id": item_id, "offer_id": offer_id, "title": title,
                "taobao_sku_count": before["taobao_count"],
                "offer_spec_count": before["offer_count"],
                "spec_source": spec_source, "offer_dims": dims,
                "count_mismatch": before["count_mismatch"],
                "duplicates": before["duplicates"],
                "unmatched": before["unmatched"],
                "status": status, "note": note, "ts": time.strftime("%F %T")}

    if args.dry_run:
        upsert(rep, item_id, item_common("dry"))
        save_report(report_path, rep)
        write_csv(args.csv, rep)
        await ensure_drawer_closed(fr)
        log(f"   [dry] 淘宝{before['taobao_count']}SKU vs 1688{offer_count if offer_count is not None else '?'}"
            f"({spec_source}) 未匹配{len(before['unmatched'])} 重复{len(before['duplicates'])}")
        return "dry"

    # apply：点「自动匹配规格」→ 回读 → 确认
    if not await click_drawer_btn(fr, "自动匹配规格"):
        if not await drawer_open(fr):
            # 按钮没点上但抽屉已不在（上轮自关残留）→ 重开再试一次
            if not await open_match_drawer(fr, item_id):
                return record_fail("reopen_fail")
            if not await click_drawer_btn(fr, "自动匹配规格"):
                st = record_fail("no_auto_btn")
                await ensure_drawer_closed(fr)
                return st
        else:
            st = record_fail("no_auto_btn")
            await ensure_drawer_closed(fr)
            return st
    await asyncio.sleep(3)
    await dismiss_confirm_dialog(fr)

    if not await drawer_open(fr):
        # 试点实测：点完「自动匹配规格」平台自动应用并自关抽屉 → 读列表行状态判定
        cell = await row_match_status(fr, item_id)
        if cell and "已匹配" in cell and "部分" not in cell:
            it = item_common("ok", "auto_closed")
            it["after"] = {"matched": before["taobao_count"] - len(before["unmatched"]),
                           "unmatched": before["unmatched"]}
            upsert(rep, item_id, it)
            save_report(report_path, rep)
            write_csv(args.csv, rep)
            log(f"   [ok] 自动匹配后平台自关抽屉, 列表状态={cell}")
            return "ok"
        # 非已匹配(或读不到) → 重开抽屉读明细走正常确认路径
        if not await open_match_drawer(fr, item_id):
            return record_fail("reopen_fail")

    drows2 = await read_drawer_rows(fr) or []
    after = analyze_rows(drows2, specs, offer_count)
    if after["unmatched"]:
        status = "manual_needed"
    elif after["count_mismatch"]:
        status = "count_mismatch"
    elif after["duplicates"]:
        status = "sku_duplicate"
    else:
        status = "ok"
    saved = await click_drawer_btn(fr, "确认")
    await asyncio.sleep(2)
    if await drawer_open(fr):          # 确认没生效
        await dismiss_confirm_dialog(fr)
        if await drawer_open(fr):
            await ensure_drawer_closed(fr)
            saved = False
    if saved:
        it = item_common(status)
    else:
        st = record_fail("confirm_fail")
        log(f"   [confirm_fail] 自动匹配后 未匹配{len(after['unmatched'])} 重复{len(after['duplicates'])}")
        return st
    it["after"] = {"matched": after["taobao_count"] - len(after["unmatched"]),
                   "unmatched": after["unmatched"]}
    it["unmatched"] = after["unmatched"]        # 终态以自动匹配后的为准
    it["duplicates"] = after["duplicates"]
    it["taobao_sku_count"] = after["taobao_count"]
    upsert(rep, item_id, it)
    save_report(report_path, rep)
    write_csv(args.csv, rep)
    log(f"   [{status}] 自动匹配后 未匹配{len(after['unmatched'])} "
        f"重复{len(after['duplicates'])} 保存OK")
    return status


async def run(args):
    rep = load_report(args.report)
    done_skip = set() if args.force else \
        {i["item_id"] for i in rep["items"] if i.get("status") in FINAL}
    log(f"{'DRY-RUN' if args.dry_run else 'APPLY'} | 报告已终态 {len(done_skip)} | "
        f"gap={args.gap} limit={args.limit or '全部'}")
    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container", "isv-container",
                                                "taobao.com", "1688.com"], log=log)
    processed = 0
    drawer_fail_streak = 0
    try:
        page = await open_page(ctx, quiet=True)
        fr = await get_frame(page)
        if not fr:
            log("!! 没找到 isv-container iframe（登录态掉了？）")
            return 2
        # 已在商品管理列表则不重复导航（导航回退路径不稳）
        if not await fr.locator(".ant-table-row").first.count():
            await nav_to_guanli(fr)
        # 快捷筛选：chip 文本带计数后缀，前缀匹配（全等匹配不到）
        for attempt in (1, 2):
            ok = await fr.evaluate(r"""() => {
              const els=[...document.querySelectorAll('*')].filter(e=>{
                const t=(e.textContent||'').trim();
                return t.startsWith('已关联货源') && t.length<20 && e.children.length<=2;});
              if(!els.length) return false;
              els[els.length-1].click(); return true;
            }""")
            await asyncio.sleep(4)
            body = await fr.inner_text("body")
            total = read_total(body)
            if ok and total and total > 2000:
                break
            log(f"   快捷筛选未生效(点击={ok}, 共{total}条)，重试 {attempt}/2")
        pages = (total + 19) // 20 if total else 1
        log(f"已关联货源 {total} 条 / {pages} 页")
        want_ids = set(args.ids.split(",")) if args.ids else None
        prev_first = None
        for pg in range(1, pages + 1):
            if pg > 1:
                await click_page(fr, pg)
                await asyncio.sleep(3)
                if not read_total(await fr.inner_text("body")):
                    await click_next(fr)
                    await asyncio.sleep(3)
                rows = await fr.evaluate(ROWS_JS)
                # 验证翻页真生效（Chrome 重启后新会话 SPA 渲染慢，3s 可能没换页——实测踩过：
                # 未生效就中止会以 rc=0 假完工）。没变就 click_next 重试 3 次，仍不变 rc=5 交 wrapper 重来。
                tries = 0
                while rows and prev_first and rows[0].get("taobao_item_id") == prev_first and tries < 3:
                    tries += 1
                    log(f"   翻页未生效，重试 {tries}/3 (click_next)")
                    await click_next(fr)
                    await asyncio.sleep(4)
                    rows = await fr.evaluate(ROWS_JS)
                if rows and prev_first and rows[0].get("taobao_item_id") == prev_first:
                    log("!! 翻页反复未生效，本轮退出 rc=5（wrapper 将重试）")
                    return 5
            else:
                rows = await fr.evaluate(ROWS_JS)
            if rows:
                prev_first = rows[0].get("taobao_item_id")
            log(f"--- 第 {pg}/{pages} 页, {len(rows)} 行 ---")
            for r in rows:
                if args.limit and processed >= args.limit:
                    log(f"已达 --limit {args.limit}，停止")
                    return 0
                item_id = str(r.get("taobao_item_id") or "")
                if not item_id:
                    continue
                if want_ids and item_id not in want_ids:
                    continue
                if item_id in done_skip:
                    continue
                log(f"[{processed + 1}] {item_id} {title_from_row_text(r.get('text', ''))[:30]}")
                st = await process_row(fr, r, args, rep, args.report)
                processed += 1
                if st == "drawer_fail":
                    drawer_fail_streak += 1
                    if drawer_fail_streak >= 5:
                        log("!! 连续 5 个抽屉失败，疑似风控/登录态，停止本轮")
                        return 3
                else:
                    drawer_fail_streak = 0
                    await asyncio.sleep(args.gap)
            if total and pg * 20 >= total:
                break
        n = write_csv(args.csv, rep)
        log(f"完成：本轮处理 {processed} 个，人工清单 {args.csv}（{n} 行）")
        try:
            from import_offer_map import refresh_table
            m = refresh_table(rep.get("items") or [])
            log(f"taobao_offer_map 已刷新（{m} 行）")
        except Exception as e:  # 刷新失败不影响匹配任务退出码，页面只是暂时用旧映射
            log(f"!! taobao_offer_map 刷新失败（不影响本轮结果）：{e}")
        return 0
    finally:
        try:
            await b.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=None, help="逗号分隔淘宝 itemId，只跑这些（试点/补跑）")
    ap.add_argument("--limit", type=int, default=0, help="本轮最多处理多少商品")
    ap.add_argument("--gap", type=float, default=10.0, help="商品之间间隔秒数")
    ap.add_argument("--force", action="store_true", help="忽略历史终态，全量重来")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="只读+记录+取消关抽屉，不保存")
    g.add_argument("--apply", action="store_true", help="点自动匹配规格+确认保存")
    a = ap.parse_args()
    if not a.apply:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
