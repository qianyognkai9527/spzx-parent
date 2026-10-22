#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isv_sync_verify.py — ISV 同步后 0 库存行级核验（spec 2026-10-18 P4）。

对本地 0 库存且存活的绑定商品逐个开控制台行级「同步记录」弹窗，
证明「1688没货 → 淘宝被推成0」真实发生；无记录/失败写告警。
用法: $PY isv_sync_verify.py --cap 50 [--dry-run]

--dry-run: 不写库、不点「同步记录」（只走 chip+搜索+定位到行）；
           真开弹窗留给 Task 11 探针。
"""
import argparse, asyncio, random, re, sys, time, traceback
import pymysql
sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG
from cdp_utils import connect_cdp
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli, query, CLICK_RESET_JS
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
    """本地 0 库存活绑定商品（任一 SKU stock=0 即危险；目标数超 cap 时 ORDER BY RAND()
    随机抽，防止无序 LIMIT 造成尾部目标永久盲区）+ 对照随机 10 个纯非零。
    对照池排除混合库存商品（既有0又有非0）——探针实证混库行在「已关联货源」视图
    搜不到，会沉淀成假 verdict=3（2026-10-18）。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT tm.taobao_item_id, tm.offer_id FROM taobao_offer_map tm "
        "JOIN source_product sp ON sp.id = tm.source_product_id AND sp.is_deleted=0 AND sp.source_status=1 "
        "WHERE EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.is_deleted=0 "
        "AND ss.status=1 AND ss.stock=0) ORDER BY RAND() LIMIT %s", (cap,))
    zeros = cur.fetchall()
    cur.execute(
        "SELECT tm.taobao_item_id, tm.offer_id FROM taobao_offer_map tm "
        "JOIN source_product sp ON sp.id = tm.source_product_id AND sp.is_deleted=0 AND sp.source_status=1 "
        "AND EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.is_deleted=0 "
        "AND ss.status=1 AND ss.stock>0) "
        "AND NOT EXISTS (SELECT 1 FROM source_sku ss2 WHERE ss2.source_product_id=sp.id AND ss2.is_deleted=0 "
        "AND ss2.status=1 AND ss2.stock=0) ORDER BY RAND() LIMIT 10")
    control = cur.fetchall()
    cur.close()
    return zeros, control


async def select_linked_chip(fr):
    """快捷筛选「已关联货源」chip：文本带计数后缀（如 已关联货源(4183)）须前缀匹配，
    先点「重置」防 SPA 筛选跨会话残留（isv_stock_sync 同款 JS）。"""
    await fr.evaluate(CLICK_RESET_JS)
    await asyncio.sleep(2)
    await fr.evaluate("""() => {
      const els=[...document.querySelectorAll('*')].filter(e=>{
        const t=(e.textContent||'').trim();
        return t.startsWith('已关联货源') && t.length<20 && e.children.length<=2;});
      if(els.length) els[els.length-1].click();}""")
    await asyncio.sleep(4)


async def search_item_row(fr, item_id):
    """搜索框搜店铺商品ID并返回定位到的行。
    input#shopProductIds 优先（淘宝 itemId 是店铺商品ID），输入框缺失回退 searchKey；
    query() 顺带清空另两个输入框，防上次搜索残留。"""
    await query(fr, shop_ids=str(item_id))
    val = await fr.evaluate(
        "() => { const i=document.querySelector('input#shopProductIds'); return i ? i.value : ''; }")
    if val != str(item_id):
        await query(fr, search_key=str(item_id))
    return fr.locator(".ant-table-row", has_text=f"ID：{item_id}").first


async def read_layer_text(fr, timeout_s=15):
    """轮询读「同步记录」弹层正文。抽屉优先（Task 11 实证：入口打开的是右侧抽屉
    .product-sync-record-drawer，.ant-drawer-open 态，class 可能挂在 wrapper 或 content，
    正文在 .ant-drawer-body / .ant-drawer-wrapper-body）→ 泛化 .ant-drawer-open
    → 降级 .ant-modal（旧路径保留）。
    就绪判据：抽屉会先渲染「表头+暂无数据」空态、记录数据异步后到（2026-10-18 重跑
    实证：有 10 条记录的商品也先读到空态 → 非空即返=假 verdict 2），故须等到文本含
    「同步为/失败/异常」才返回；真无记录的商品超时后返回空态文本（→verdict 2，方向安全）。"""
    last = None
    for _ in range(timeout_s * 2):
        t = await fr.evaluate("""() => {
          const vis = e => e.getClientRects().length > 0;
          for (const d of document.querySelectorAll('.product-sync-record-drawer')) {
            if (!d.closest('.ant-drawer-open')) continue;
            const body = d.querySelector('.ant-drawer-body') || d.querySelector('.ant-drawer-wrapper-body');
            if (body && vis(body)) return (body.innerText||'');
          }
          for (const d of document.querySelectorAll('.ant-drawer-open')) {
            const body = d.querySelector('.ant-drawer-body');
            if (body && vis(body)) return (body.innerText||'');
          }
          const m = document.querySelector('.ant-modal:not([style*="display: none"]) .ant-modal-body');
          if (m && vis(m)) return (m.innerText||'');
          return null; }""")
        if t and t.strip():
            last = t
            if "暂无数据" not in t and ("同步为" in t or "失败" in t or "异常" in t):
                return t
        await asyncio.sleep(0.5)
    return last


async def close_record_layer(fr):
    """关「同步记录」弹层：点 .ant-drawer-close（真点击 force；**绝不用键盘 Escape**，
    事件到不了 iframe——sourcing 抽屉红线）等 .ant-drawer-open 消失；旧 modal 路径
    点 .ant-modal-close + S.wait_no_modal 兜底。"""
    for _ in range(3):
        if not await fr.evaluate("() => !!document.querySelector('.ant-drawer-open')"):
            return True
        clicked = False
        for sel in (".ant-drawer-open .product-sync-record-drawer .ant-drawer-close",
                    ".ant-drawer-open .ant-drawer-close"):
            loc = fr.locator(sel).first
            if await loc.count():
                try:
                    await loc.click(timeout=2500, force=True)
                    clicked = True
                except Exception:
                    await fr.evaluate("""() => {
                      const c=document.querySelector('.ant-drawer-open .product-sync-record-drawer .ant-drawer-close')
                             || document.querySelector('.ant-drawer-open .ant-drawer-close');
                      if(c) c.click(); }""")
                    clicked = True
                break
        await asyncio.sleep(1.5)
        if not clicked:
            break
    if not await fr.evaluate("() => !!document.querySelector('.ant-drawer-open')"):
        return True
    try:
        await fr.evaluate("""() => {
          const c=document.querySelector('.ant-modal:not([style*="display: none"]) .ant-modal-close');
          if(c) c.click(); }""")
        await asyncio.sleep(1.5)
    except Exception:
        pass
    await S.wait_no_modal(fr)
    return not await fr.evaluate("() => !!document.querySelector('.ant-drawer-open')")


async def read_row_sync_record(fr, item_id, open_modal=True):
    """控制台「已关联货源」chip + 搜索框搜 itemId -> 定位该行 ->（可选）打开行级
    「同步记录」弹层 -> 返回弹层文本。

    行定位/入口选择器同 isv_sku_match.open_match_drawer：先试行内内联「同步记录」
    （Task 11 实证 3/3 都是内联入口，无需「更多」下拉），没有再走 更多 下拉兜底；
    弹层是右侧抽屉 .product-sync-record-drawer（读层/关层见 read_layer_text /
    close_record_layer，modal 仅作降级路径），读完关闭再返回。
    open_modal=False 只定位行不开弹层（dry-run 冒烟路径，真开弹层留给探针）。
    """
    await select_linked_chip(fr)
    row = await search_item_row(fr, item_id)
    try:
        await row.wait_for(state="visible", timeout=8000)
    except Exception:
        # 搜索偶发竞态（冒烟/Task 11 均有「行未渲染」假阴性）：隔 3s 重搜一次再判
        await asyncio.sleep(3)
        row = await search_item_row(fr, item_id)
        try:
            await row.wait_for(state="visible", timeout=8000)
        except Exception as e:
            raise RuntimeError(f"行未渲染(已关联货源里搜不到 ID：{item_id}, 含重搜): {str(e)[:80]}")
    if not open_modal:
        return None
    entry = row.locator("text=同步记录").first
    if not await entry.count():
        await row.locator("text=更多").first.click(timeout=6000)
        await asyncio.sleep(1.2)
        entry = fr.locator(".ant-dropdown:not(.ant-dropdown-hidden)").locator("text=同步记录").first
    await entry.click(timeout=6000)
    text = await read_layer_text(fr)
    await close_record_layer(fr)
    if not text:
        raise RuntimeError("同步记录弹层未出现或内容为空(抽屉+modal 双路径)")
    return text


async def verify_items(conn, targets, dry=False):
    b, ctx = await connect_cdp(9222, keep_urls=["taobao.com", "1688.com"], log=log, minimize=True)
    page = None
    results = []
    try:
        page = await open_page(ctx, quiet=True)
        fr = await get_frame(page)
        if not fr:
            raise RuntimeError("没找到 isv-container iframe（9222 登录态掉了？）")
        if not await fr.locator(".ant-table-row").first.count():
            await nav_to_guanli(fr)
            for _ in range(30):   # nav 后表格偶发 8s 内不渲染（Task 11 实证），长轮询兜底
                if await fr.locator(".ant-table-row").first.count():
                    break
                await asyncio.sleep(1)
        cur = conn.cursor()
        for item_id, offer_id in targets:
            now = time.strftime("%F %T")   # 逐条取时（Task 11：循环外取一次全表同刻）
            try:
                text = await read_row_sync_record(fr, str(item_id), open_modal=not dry)
                if text is None:   # dry-run：已定位到行，未开弹窗
                    results.append({"item": item_id, "offer": offer_id, "verdict": None,
                                    "text": "dry-run: 已定位行，未开弹窗", "nums": []})
                    log(f"  {item_id}: dry-run 已定位行")
                    continue
                verdict, nums = parse_sync_record(text)
                log(f"  {item_id}: verdict={verdict} nums={nums} {(text or '')[:60]!r}")
            except Exception as e:
                text, verdict, nums = str(e)[:200], 3, []
                log(f"  {item_id}: 异常 verdict=3 {text[:80]}")
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
        try:
            if page:
                await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass
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
        if not zeros:
            log("本地 0 库存且存活的绑定商品为 0 条（库内现状），无危险行需核验，正常退出。")
            conn.close()
            return
        results = asyncio.get_event_loop().run_until_complete(verify_items(conn, zeros + control, args.dry_run))
        n1 = sum(1 for r in results if r["verdict"] == 1)
        n2 = sum(1 for r in results if r["verdict"] == 2)
        n3 = sum(1 for r in results if r["verdict"] == 3)
        nd = sum(1 for r in results if r["verdict"] is None)
        log(f"核验完成: 判定 1={n1} 2={n2} 3={n3} dry未开弹窗={nd}")
        zero_ids = {str(z[0]) for z in zeros}
        if not args.dry_run:
            alert_failures(conn, [r for r in results
                                  if r["verdict"] not in (1, None) and str(r["item"]) in zero_ids])
        conn.close()
    except Exception:
        traceback.print_exc(); sys.exit(1)

if __name__ == "__main__":
    main()
