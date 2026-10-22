#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 发布: 按 pdd_worklist.jsonl 逐个在 mms 后台发布穿戴甲, 断点续跑.
跑法: automation/venv/bin/python create_pdd_product.py [--retry-failed] [--limit N] [--test]
  --test: 走到 Step2 完整表单即停(不提交), dump 到 pdd_notes/step2_dump_<id>.txt
进度: pdd_create_progress.json {done:[], failed:{}, skipped:[]}
流程(2026-09-30 探路): /goods/category 上传主图+标题 -> Tab 触发推荐 -> 点「查看更多推荐」
 -> 点目标类目 -> 下一步 -> /goods/goods_add/index 完整表单 -> 填表 -> 提交并上架
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402
import pdd_compliance as G  # noqa: E402
import pdd_map  # noqa: E402


def log(m):
    print(m, flush=True)


# PDD 风控/验证关键词: 命中即判定风控, 退出码 42 交给外层冷却
RISK_KW = ("操作频繁", "操作过于频繁", "请求过于频繁", "当前操作存在风险", "RGV587",
           "FAIL_SYS_USER_VALIDATE", "captchacappuzzle", "x5sec", "环境异常")
# 可人工通过的验证码关键词: 命中则等待人工在窗口过验证(不直接判失败)
CAPTCHA_KW = ("请沿图中路径绘制", "沿图中路径", "绘制", "滑块", "拖动滑块",
              "滑动验证", "验证码", "请完成验证", "安全验证")


def _hit(body, kws):
    for k in kws:
        if k in body:
            return k
    return None


def _risk_txt(body):
    return _hit(body, RISK_KW)


def record_pdd_product(page_url, rec):
    """成功时落盘 PDD goods_id, 供后续导入关联."""
    m = re.search(r"goods_id=(\d+)", page_url)
    if not m:
        return
    row = {"pdd_goods_id": m.group(1), "item_id": rec["item_id"],
           "title": rec["title"], "price": rec["price"], "images": rec["images"]}
    with open(C.PDD_PRODUCTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


TITLE_SEL = "input[placeholder*='商品标题组成']"
RECO_JS = "() => (document.body.innerText||'').includes('查看更多推荐')"
TITLE_VALUE_JS = ("() => { const el=document.querySelector(\"input[placeholder*='商品标题组成']\"); "
                  "return el ? el.value : ''; }")
# (n/10) 且 n>=1：老写法的 \(\d+/10\) 会把 (0/10) 也匹配掉，等于上传失败也判成功
UPLOADED_JS = "() => /\\([1-9]\\d*\\/10\\)/.test(document.body.innerText||'')"


async def upload_images(page, files, settle=4, log=None):
    """上传主图。PDD 2026-10-08 前端更新后上传控件不再响应 Playwright 的合成 change：
    必须 ① 等 React 挂载完成（太早填的文件会被页面自身的异步逻辑丢弃）
    ② set_input_files 之后再显式派发 input+change，否则后端一个上传请求都不发（实测）。
    返回是否成功（以页面 (n/10) 计数 n>=1 为准）。"""
    if log:
        log(f"    等页面就绪 {settle}s 后上传 {len(files)} 张图")
    await asyncio.sleep(settle)
    try:
        await page.set_input_files("input[type=file]", files)
    except Exception as e:
        if log:
            log(f"    set_input_files 失败: {str(e)[:120]}")
        return False
    try:
        await page.evaluate(
            "() => { const i=document.querySelector('input[type=file]'); if(i){"
            "i.dispatchEvent(new Event('input',{bubbles:true}));"
            "i.dispatchEvent(new Event('change',{bubbles:true})); } }")
    except Exception:
        pass
    ok = await wait_until(page, UPLOADED_JS, 30, step=0.5, log=log)
    if not ok and log:
        log("    ⚠ 30s 内主图计数仍为 0/10，上传可能失败")
    return ok


async def ensure_category_recommendations(page, title, timeout_each=8, tries=3, log=None):
    """填标题 -> Tab -> 等类目推荐区渲染。返回是否等到。

    为什么要回读标题再重试：新加的"事件等待"让流程跑得比页面准备得早 —— 上传指示一出现就立刻填标题时，
    页面自身的异步逻辑会把值清掉，于是 Tab 白按、推荐区整页不渲染（实测等 30 秒也没有，
    而同一件商品在网络探针里 3 秒就有）。回读发现标题不在，就重填重按，而不是把超时调大。
    """
    for attempt in range(1, tries + 1):
        cur = ""
        try:
            cur = await page.evaluate(TITLE_VALUE_JS)
        except Exception:
            pass
        if (cur or "").strip() != title.strip():
            await page.fill(TITLE_SEL, title)
            if log:
                shown = (cur or "")[:12]
                log(f"    标题没落进输入框(读回={shown})，重填后重试(第{attempt}次)")
        await page.keyboard.press("Tab")
        if await wait_until(page, RECO_JS, timeout_each, step=0.5):
            return True
    return False


async def reach_step2(page, rec):
    """Step1: 上传主图+标题+选类目 -> 下一步. 返回 True 到 Step2."""
    await page.goto(C.MMS_GOODS_PUBLISH, wait_until="domcontentloaded", timeout=40000)
    # 等上传控件出现即可，别赌 5 秒
    if not await wait_until(page, "() => !!document.querySelector('input[type=file]')", 25, log=log):
        await asyncio.sleep(5)
    if not rec["images"]:
        return False
    await upload_images(page, rec["images"], log=log)
    if C.FAST_WAIT:
        await ensure_category_recommendations(page, rec["title"], log=log)
    else:
        await page.fill(TITLE_SEL, rec["title"])
        await page.keyboard.press("Tab")
        # 等异步类目推荐（AGENTS.md：类目推荐是异步的、渲染有波动）
        for _ in range(15):
            await asyncio.sleep(2)
            if await page.evaluate(RECO_JS):
                break
    # 展开推荐
    await page.evaluate("""() => { const e=[...document.querySelectorAll('*')].find(x=>(x.textContent||'').trim()==='查看更多推荐'); if(e)e.click(); }""")
    if C.FAST_WAIT:
        # 等目标类目真的出现在推荐里，而不是固定睡 3 秒后再找
        target = json.dumps(C.TARGET_CATEGORY)
        await wait_until(page, f"() => [...document.querySelectorAll('*')].some(e=>(e.textContent||'').trim()==={target})",
                         15, step=0.5, log=log)
    else:
        await asyncio.sleep(3)
    # 点目标类目
    r = await page.evaluate("""(t) => { const el=[...document.querySelectorAll('*')].find(e=>(e.textContent||'').trim()===t); if(!el) return false; el.click(); return true; }""", C.TARGET_CATEGORY)
    if not r:
        return False
    await asyncio.sleep(2)
    await page.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(x=>(x.innerText||'').includes('下一步')); if(b)b.click(); }""")
    if C.FAST_WAIT:
        # 跳进 Step2 才算数，等到就往下走
        await wait_until(page, "() => location.href.includes('/goods/goods_add')", 30, step=0.5, log=log)
    else:
        await asyncio.sleep(8)
    return "/goods/goods_add" in page.url


async def js_click(page, js_cond):
    return await page.evaluate(
        """(cond) => { const el=[...document.querySelectorAll(cond.sel)].find(e=>{ let n=e; """
        """for(let i=0;i<4&&n;i++){ n=n.parentElement; if(n && (n.innerText||'').includes(cond.txt)) return true; } """
        """return false; }); if(el){ el.click(); return true; } return false; }""",
        js_cond)


async def js_click_text(page, txt):
    return await page.evaluate(
        """(t) => { const e=[...document.querySelectorAll('*')].find(x=>(x.textContent||'').trim()===t); """
        """if(e){ e.click(); return true; } return false; }""", txt)


async def fill_step2(page, rec):
    """Step2 完整表单填写. 返回 (ok, msg)."""
    stock = str(rec.get("stock") or 100)
    try:
        stock = str(min(int(stock), 1000))
    except (TypeError, ValueError):
        stock = "100"
    price = rec["price"]
    single = round(price + 1, 2)   # PDD 要求单买价 ≥ 拼单价+1
    ref = round(price * C.REF_PRICE_FACTOR, 2)   # 会显示成划线价, 口径与合规风险见 pdd_config

    # 1) 属性一键复用(PDD 自动匹配相似品属性)
    await js_click_text(page, "一键复用")
    await asyncio.sleep(2)
    # 2) 尺码全选
    await js_click(page, {"sel": "input[type=checkbox]", "txt": "全选以下规格值"})
    if C.FAST_WAIT:
        # 等价格表真出生成行，而不是固定 3 秒
        await wait_until(page, "() => { const t=[...document.querySelectorAll('table')].find(x=>(x.innerText||'').includes('拼单价')); return !!t && t.querySelectorAll('tbody tr').length>0; }",
                         15, step=0.5, log=log)
    else:
        await asyncio.sleep(3)
    # 3) 价格及库存表: 每行前3个 input = 库存/拼单价/单买价
    table = page.locator("table", has_text="拼单价").first
    rows = table.locator("tbody tr")
    n = await rows.count()
    if n == 0:
        return False, "价格表无行(尺码未生效?)"
    for i in range(n):
        row = rows.nth(i)
        ins = row.locator("input")
        await ins.nth(0).fill(stock)
        await ins.nth(1).fill(str(price))
        await ins.nth(2).fill(str(single))
        # 每行规格预览图(必传): 循环用主图
        f = row.locator("input[type=file]")
        if await f.count() and rec["images"]:
            await f.first.set_input_files(rec["images"][i % len(rec["images"])])
            await asyncio.sleep(1)
    # 4) 商品参考价(须大于最大单买价)
    ref_in = page.locator("input[placeholder*='应大于']").first
    if await ref_in.count():
        await ref_in.fill(str(ref))
    # 5) 承诺发货时间=48小时
    await js_click(page, {"sel": "input[type=radio]", "txt": "48小时发货及揽收"})
    # 6) 7天无理由(该类目必选)
    await js_click(page, {"sel": "input[type=checkbox]", "txt": "7天无理由退货"})
    await asyncio.sleep(1)
    return True, f"已填: 尺码x{n} 库存{stock} 拼单价{price} 单买价{single} 参考价{ref}"


async def publish_one(page, rec, do_submit, captcha_attempt=1):
    ok = await reach_step2(page, rec)
    if not ok:
        rk = _risk_txt(await page.inner_text("body"))
        if rk:
            return "risk", f"Step1 风控: {rk}"
        return "fail", "未进入 Step2(类目/上传失败)"
    fok, fmsg = await fill_step2(page, rec)
    if not fok:
        rk = _risk_txt(await page.inner_text("body"))
        if rk:
            return "risk", f"Step2 风控: {rk}"
        return "fail", fmsg
    if not do_submit:
        body = await page.inner_text("body")
        os.makedirs(C.NOTES, exist_ok=True)
        open(os.path.join(C.NOTES, f"step2_filled_{rec['item_id']}.txt"), "w", encoding="utf-8").write(f"URL: {page.url}\n\n{body}")
        return "fail", "test: 已填 Step2, 未提交 | " + fmsg
    # 提交并上架
    await page.locator("button", has_text="提交并上架").first.click()
    err = None
    cap = None
    for _ in range(20):
        await asyncio.sleep(1.5)
        if "success" in page.url or "goods_list" in page.url:
            record_pdd_product(page.url, rec)
            return "ok", "已上架(跳转成功页) | " + fmsg
        body = await page.inner_text("body")
        ck = _hit(body, CAPTCHA_KW)
        if ck:
            cap = ck
            break
        rk = _risk_txt(body)
        if rk:
            return "risk", f"提交风控: {rk}"
        for kw in ("商详装修校验", "请重新上传", "请上传", "不能为空", "发布失败", "提交失败", "图片宽度应为"):
            if kw in body:
                err = kw
                break
        if err:
            break
    if cap:
        wait_s = captcha_wait_seconds(captcha_attempt)
        if wait_s == 0:
            log(f"  ⚠ 触发验证码[{cap}], 该商品第 {captcha_attempt} 次卡住, 不再等待, 直接隔离")
            return "captcha", f"验证码未通过/提交无果[{cap}](第{captcha_attempt}次, 未等待) | {fmsg}"
        log(f"  ⚠ 触发验证码[{cap}], 请在 9224 窗口手动过验证(最多等 {wait_s}s, 第 {captcha_attempt} 次)...")
        for _ in range(max(1, wait_s // 3)):
            await asyncio.sleep(3)
            if "success" in page.url or "goods_list" in page.url:
                record_pdd_product(page.url, rec)
                return "ok", "已上架(过验证后) | " + fmsg
            body = await page.inner_text("body")
            if not _hit(body, CAPTCHA_KW):
                await asyncio.sleep(3)
                if "success" in page.url or "goods_list" in page.url:
                    record_pdd_product(page.url, rec)
                    return "ok", "已上架(过验证后) | " + fmsg
                break
        # 单独一个状态, 不再混进 "risk": 验证码是"这件要人点一下", 风控是"这个号被限流"。
        # 以前两者都返回 risk -> 外层退出码 42 -> 冷却后从同一件重试, 而那件永远排在队首,
        # 于是整条队列被一件卡死(10-02 17:10 到 21:04 就是这么空转了 4 轮)。
        return "captcha", f"验证码未通过/提交无果[{cap}] | {fmsg}"
    body = await page.inner_text("body")
    os.makedirs(C.NOTES, exist_ok=True)
    open(os.path.join(C.NOTES, f"submit_result_{rec['item_id']}.txt"), "w", encoding="utf-8").write(f"URL: {page.url}\n\n{body[:3000]}")
    if err:
        return "fail", f"提交被拦: {err} | {fmsg}"
    return "fail", "提交结果未知(超时30s) 见 submit_result_" + rec["item_id"] + ".txt"


async def wait_until(page, cond_js, timeout, step=0.4, log=None):
    """轮询页面直到条件成立 -> True；超时或条件本身报错 -> False。

    固定 sleep 换成这个的目的：sleep 是"赌页面一定在 N 秒内好"，赌大了白等、
    赌小了踩空。这里改成"好了就走"，踩空由超时兜底（调用方拿到 False 再决定回退还是判失败）。
    条件里取元素失败是常态（页面还没渲染），所以 evaluate 抛异常按"还没好"处理，不往上炸。
    """
    deadline = time.monotonic() + timeout
    errs = 0
    polls = 0
    while time.monotonic() < deadline:
        polls += 1
        try:
            if await page.evaluate(cond_js):
                return True
        except Exception:
            # 条件里取元素失败是常态（页面还没渲染），但**连续失败**说明是 evaluate 本身在报错
            # （例如 Tab 触发重渲染把执行上下文换掉了），那就要把它数出来，别静默等满超时
            errs += 1
        await asyncio.sleep(step)
    if log and errs:
        log(f"    ⏱ 轮询 {polls} 次失败 {errs} 次（evaluate 报错，不是条件不成立）")
    if log:
        log(f"    ⏱ 等待超时({timeout}s): {cond_js[:60]}")
    return False


def captcha_wait_seconds(attempt):
    """同一件商品第几次卡在验证码 -> 该在窗口前等多久。

    第 1 次给现场的人留窗口；第 2 次它已经要被隔离了，再盲等没有意义。
    """
    return C.CAPTCHA_WAIT_SEC if attempt <= 1 else 0


def record_captcha(prog, item_id, msg):
    """记下一次"卡在验证码", 返回 (是否隔离, 该商品累计次数).

    单独抽出来是因为它是这段逻辑里唯一能离线验证的部分 —— 另外几支都要动真实店铺。
    """
    caps = prog.setdefault("captcha", {})
    caps[item_id] = caps.get(item_id, 0) + 1
    if caps[item_id] >= C.CAPTCHA_QUARANTINE_AFTER:
        prog["failed"][item_id] = f"验证码隔离(第{caps[item_id]}次): {msg}"
        return True, caps[item_id]
    return False, caps[item_id]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--preflight", action="store_true",
                    help="只跑合规闸门并退出，不连浏览器、不改进度文件")
    ap.add_argument("--source", choices=["taobao", "1688"], default="taobao",
                    help="taobao=淘宝源 worklist; 1688=1688 直铺 worklist")
    args = ap.parse_args()
    if args.source == "1688":
        C.WORKLIST = C.WORKLIST_1688
        C.PROGRESS = C.PROGRESS_1688
        log(f"[source=1688] worklist={C.WORKLIST} progress={C.PROGRESS}")

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
    # 合规闸门：在连浏览器之前跑。拦下来的件不占页面、不产生草稿、也不消耗风控额度，
    # 所以它跟"验证码隔离"是两种性质 —— 那种重试有副作用，这种没有。
    rules = G.load_rules()["rules"]
    rejs, rwarn = G.load_json_list(C.REJECTIONS, "rejected")
    snap, swarn = G.load_json_list(C.SNAPSHOT, "on_sale")
    for warn in (rwarn, swarn):
        if warn:
            log(f"  (提示) {warn}；手工黑名单仍然生效")
    brands = G.brands_for_publish(C.BRAND_WORDS, rejs, snap)
    todo, blocked = G.filter_by_gate(todo, rules, brands)
    if blocked:
        for iid, why in blocked:
            prog["failed"][iid] = "合规闸门: " + "; ".join(why)
        if not (args.test or args.preflight):
            save_prog(prog)
        log(f"合规闸门拦下 {len(blocked)} 条（未接触浏览器），放行 {len(todo)} 条；生效品牌词 {len(brands)} 个")
        for iid, why in blocked[:10]:
            log(f"  ✗ {iid} {'; '.join(why)}")

    if args.limit:
        todo = todo[: args.limit]


    if args.preflight:
        log("preflight: 只跑闸门，未连接浏览器")
        return

    b, ctx = await connect_cdp(C.CDP_PORT, keep_urls=["pinduoduo.com"], log=log)
    page = await ctx.new_page()
    consec_fail = 0
    cap_streak = 0
    try:
        for n, rec in enumerate(todo, 1):
            if n > 1:
                await asyncio.sleep(C.ITEM_GAP_SEC)
            log(f"[{n}/{len(todo)}] item {rec['item_id']}")
            t_item = time.monotonic()
            try:
                attempt = prog.setdefault("captcha", {}).get(rec["item_id"], 0) + 1
                status, msg = await asyncio.wait_for(
                    publish_one(page, rec, not args.test, captcha_attempt=attempt), timeout=600)
            except asyncio.TimeoutError:
                status, msg = "risk", "超时600s(疑风控)"
            log(f"  ⏱ 本件耗时 {time.monotonic() - t_item:.0f}s")
            if status == "ok":
                prog["done"].append(rec["item_id"])
                prog["failed"].pop(rec["item_id"], None)
                prog.setdefault("captcha", {}).pop(rec["item_id"], None)
                consec_fail = cap_streak = 0
                if not args.test:
                    save_prog(prog)
                log("  ✓ " + msg)
            elif status == "captcha":
                quarantined, n_cap = record_captcha(prog, rec["item_id"], msg)
                cap_streak += 1
                if quarantined:
                    log(f"  ⛔ 第 {n_cap} 次卡在验证码, 隔离不再重投(重投=多一条草稿) -> {msg}")
                else:
                    log(f"  ⚠ 第 {n_cap} 次卡在验证码, 先跳过, 有人时回头补 -> {msg}")
                if not args.test:
                    save_prog(prog)
                if cap_streak >= C.CAPTCHA_STREAK_STOP:
                    log(f"  ⚠ 连续 {cap_streak} 件都要人工过验证, 判为账号级风控 -> 退出码 42")
                    sys.exit(42)
                await asyncio.sleep(C.CAPTCHA_BACKOFF_SEC)
                continue
            elif status == "risk":
                if not args.test:
                    save_prog(prog)
                log("  ⚠ 风控: " + msg + " -> 退出码 42")
                sys.exit(42)
            else:
                prog["failed"][rec["item_id"]] = msg
                consec_fail += 1
                cap_streak = 0
                if not args.test:
                    save_prog(prog)
                log("  ✗ " + msg)
                # 连续失败熔断: 静默卡住(无报错)多为配额/风控, 没必要继续空耗
                if consec_fail >= 6:
                    log("  ⚠ 连续 6 次失败, 疑配额/风控 -> 退出码 42")
                    sys.exit(42)
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
