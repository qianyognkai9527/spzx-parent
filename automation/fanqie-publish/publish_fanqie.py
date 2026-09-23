#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万域邪主》自动发布到番茄小说作家后台 (CDP 9223).

闭环: 写10章 -> novel_import.py 导入后台 -> 本脚本从后台 API 读章节
      -> 逐章发布到番茄(定时) -> 成功后标记后台 status=2(已发布).

数据源: 后台 spzx 8501 API (token 复用 Redis 中现有登录态).
发布目标: 番茄作家后台作品 7651163408473000985 (9223 Chrome 已登录).

用法:
  publish_fanqie.py --dry-run                # 只打印待发清单+排期, 不发布
  publish_fanqie.py --limit 1                # 只发 1 章 (测试用)
  publish_fanqie.py                          # 发布全部剩余章节
  publish_fanqie.py --start 12               # 从第12章开始
  publish_fanqie.py --skip-first 3           # 跳过前3章

失败即暂停: 任何一步失败脚本立即退出, 等待人工介入后重跑(断点续传).
"""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

import requests
from playwright.async_api import async_playwright

# ===== 配置 =====
CDP_URL = "http://127.0.0.1:9223"
BACKEND = "http://127.0.0.1:8501"
BOOK_ID = "7651163408473000985"
BOOK_NAME = "万域邪主"
PUBLISH_HOUR = 12  # 每天定时发布时刻
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_progress.json")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fanqie_publish_state.json")

# 番茄发布页相关 selector
PUBLISH_URL = f"https://fanqienovel.com/main/writer/{BOOK_ID}/publish/?enter_from=newchapter"
CHAPTER_MANAGE_URL = f"https://fanqienovel.com/main/writer/chapter-manage/{BOOK_ID}&{BOOK_NAME}?type=1"


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ===== 后端 API 交互 =====

def get_backend_token():
    """从 Redis 找一个有效的后台登录 token."""
    keys = subprocess.run(
        ["/opt/homebrew/bin/redis-cli", "-h", "127.0.0.1", "-p", "6379", "KEYS", "user:login:*"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    candidates = []
    for k in keys:
        tk = k.replace("user:login:", "").strip()
        if "validatecode" in tk or "test_" in tk:
            continue
        if len(tk) == 32:
            candidates.append(tk)
    for tk in candidates:
        try:
            r = requests.get(
                f"{BACKEND}/admin/novel/chapter/findByPage",
                params={"pageNum": 1, "pageSize": 1},
                headers={"token": tk}, timeout=10,
            )
            if r.json().get("code") == 200:
                return tk
        except Exception:
            continue
    return None


def fetch_all_chapters(token):
    """从后台拉全部章节, 按 chapterNum 升序."""
    out, page, size = [], 1, 50
    while True:
        r = requests.get(
            f"{BACKEND}/admin/novel/chapter/findByPage",
            params={"pageNum": page, "pageSize": size, "novelId": 1},
            headers={"token": token}, timeout=15,
        )
        data = r.json()
        if data.get("code") != 200:
            raise RuntimeError(f"findByPage 失败: {data.get('message')}")
        records = data["data"]["records"]
        if not records:
            break
        out.extend(records)
        if len(records) < size:
            break
        page += 1
    out.sort(key=lambda c: c["chapterNum"])
    return out


def mark_published(token, chapter_id):
    """调用后台 markPublished 接口把章节标记为已发布."""
    r = requests.put(
        f"{BACKEND}/admin/novel/chapter/markPublished/{chapter_id}",
        headers={"token": token}, timeout=15,
    )
    return r.json().get("code") == 200


# ===== 进度文件 =====

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": [], "failed": [], "scheduled": {}}


def save_progress(prog):
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_FILE)


def save_fanqie_state(chapters, fanqie_max, sched, prog):
    """把每章番茄发布状态持久化到 fanqie_publish_state.json (供后台看板只读聚合)."""
    failed_map = {}
    for f in prog.get("failed", []):
        failed_map[f["chapterNum"]] = f.get("error")
    # 配额耗尽(临时): 本次未能提交的章节应视为 pending 而非 failed, 明天重试
    quota_blocked = bool(prog.get("quota_blocked"))
    done_set = set(prog.get("done", []))
    chapters_state = {}
    for c in chapters:
        num = c["chapterNum"]
        if num <= fanqie_max or num in done_set:
            chapters_state[str(num)] = {"schedule": sched.get(num), "status": "published", "error": None}
        elif num in failed_map and not quota_blocked:
            chapters_state[str(num)] = {"schedule": sched.get(num), "status": "failed", "error": failed_map[num]}
        else:
            chapters_state[str(num)] = {"schedule": sched.get(num), "status": "pending", "error": None}
    state = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fanqieMax": fanqie_max,
        "chapters": chapters_state,
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)
    log(f"✓ 番茄发布状态已写入 {STATE_FILE}")


# ===== 排期计算 =====

def build_schedule(all_nums, today_12_ok):
    """从 fanqie_max+1 起的全部章节号, 每3章一天, 从今天12点起逐天排.

    day_offset = 序号(i) // 3: 第8,9,10章(i=0,1,2)->今天, 第11,12,13章(i=3,4,5)->明天...
    已发/已排章节也占用槽位(由调用方跳过发布), 保证每天3章的连续节奏.
    若今天12点已过则整体顺延一天.
    """
    base = date.today()
    if not today_12_ok:
        base += timedelta(days=1)
    sched = {}
    for i, num in enumerate(all_nums):
        day = base + timedelta(days=i // 3)
        sched[num] = f"{day.isoformat()} 12:00"
    return sched


# ===== 番茄 CDP 交互 =====

def pick_backend_chapters(chapters, fanqie_max):
    """以番茄已发布最大章号为基准, 选出待发章节(严格升序)."""
    return [c for c in chapters if c["chapterNum"] > fanqie_max and c.get("status") != 2]


async def get_fanqie_max_chapter(page):
    """读番茄章节管理页『已发布/待发布/审核中』章节的最大章节号.

    翻页遍历所有分页(每页15条), 取全部已占用章号的最大值.
    """
    import re
    await page.goto(CHAPTER_MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(7000)
    max_pub = 0
    seen_pages = set()
    for page_idx in range(1, 50):  # 安全上限
        rows = await page.evaluate("""
        () => {
          const out=[];
          document.querySelectorAll('tr').forEach(tr=>{
            const t=(tr.innerText||'').trim();
            if(t && /第\\d+章/.test(t)) out.push(t);
          });
          return out;
        }
        """)
        cur_max = 0
        for r in rows:
            m = re.search(r"第(\d+)章", r)
            if not m:
                continue
            num = int(m.group(1))
            # 已发布/待发布/审核中 都视为已被番茄占用, 不能重复发布
            if ("已发布" in r or "待发布" in r or "审核中" in r) and "草稿" not in r:
                if num > cur_max:
                    cur_max = num
        if cur_max > max_pub:
            max_pub = cur_max
        # 尝试翻下一页: 找未激活的数字页码
        next_num = page_idx + 1
        clicked = await page.evaluate("""(n) => {
          const items=[...document.querySelectorAll('.arco-pagination-item')];
          const it = items.find(e=>(e.innerText||'').trim()===String(n)
            && !/arco-pagination-item-active/.test(e.className) && !/disabled/.test(e.className));
          if(!it) return false;
          it.click(); return true;
        }""", next_num)
        if not clicked:
            break
        await page.wait_for_timeout(4000)
        if page_idx in seen_pages:
            break
        seen_pages.add(page_idx)
    return max_pub


async def fill_prosemirror(page, text):
    """向 ProseMirror 正文编辑器注入文本 (ClipboardEvent paste)."""
    return await page.evaluate("""(txt) => {
      const ed = document.querySelector('.ProseMirror');
      if(!ed) return false;
      ed.focus();
      const dt = new DataTransfer();
      dt.setData('text/plain', txt);
      ed.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
      return true;
    }""", text)


async def publish_one_chapter(browser, chapter, sched_time, token):
    """发布单个章节, 成功返回 True, 失败抛异常(暂停)."""
    num = chapter["chapterNum"]
    title = chapter["title"]
    content = chapter["content"]
    chapter_id = chapter["id"]
    # 校验
    if len(content) < 1000:
        raise RuntimeError(f"第{num}章《{title}》正文 {len(content)}字 < 1000, 番茄要求≥1000字, 中止运行等待人工处理")

    ctx = browser.contexts[0]
    page = await ctx.new_page()
    try:
        # 1. 打开发布页
        await page.goto(PUBLISH_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(7000)

        # 2. 填章节号 / 标题 / 正文
        num_input = page.locator("input.byte-input-size-default:not([placeholder])")
        await num_input.fill(str(num))
        await page.locator("input[placeholder='请输入标题']").fill(title)
        ok = await fill_prosemirror(page, content)
        if not ok:
            raise RuntimeError("ProseMirror 编辑器未找到, 无法填正文")
        await page.wait_for_timeout(2500)

        # 3. 下一步
        await page.click("text=下一步", timeout=10000)
        await page.wait_for_timeout(3000)

        # 3.5 错别字确认弹窗: "检测到你还有错别字未修改, 是否确定提交?" -> 点「提交」
        #     (含错别字的章节下一步后先弹此窗, 不处理会卡在编辑页)
        typo_clicked = False
        for _ in range(4):
            typo_ok = await page.evaluate("""() => {
              const all=[...document.querySelectorAll('*')];
              const parent = all.find(el => (el.innerText||'').includes('错别字')
                && el.childElementCount>0 && el.children.length<10);
              if(!parent) return false;
              const b=[...parent.querySelectorAll('button')].find(x=>(x.innerText||'').trim()==='提交');
              if(!b) return false;
              b.click(); return true;
            }""")
            if not typo_ok:
                break
            typo_clicked = True
            await page.wait_for_timeout(1500)
        if typo_clicked:
            log(f"  · 第{num}章存在错别字提示, 已确认继续")
        await page.wait_for_timeout(3000)

        # 4. 内容检测: 出现「仅基础检测」就点它; 否则可能已直接进入发布设置
        det_ok = await page.evaluate("""() => {
          const els=[...document.querySelectorAll('*')].filter(el=>el.childElementCount===0
            && (el.innerText||'').trim()==='仅基础检测');
          if(els.length){ els[0].click(); return true; }
          return false;
        }""")
        if det_ok:
            log(f"  · 第{num}章选择「仅基础检测」")
            await page.wait_for_timeout(8000)
        # 确认已到发布设置(定时发布开关存在)
        sw_present = await page.evaluate("""() => {
          const help=document.querySelector('.publish-confirm-timed-help');
          return !!help;
        }""")
        if not sw_present:
            body = await page.evaluate("document.body.innerText")
            raise RuntimeError("未进入发布设置(找不到定时发布开关), 可能上一步校验未通过")

        # 5. 开定时发布
        sw_ok = await page.evaluate("""() => {
          const help=document.querySelector('.publish-confirm-timed-help');
          if(!help) return false;
          const parent=help.parentElement;
          const sw=parent.querySelector('button.arco-switch');
          if(!sw) return false;
          if(sw.getAttribute('aria-checked')==='true') return true;
          sw.click(); return true;
        }""")
        if not sw_ok:
            raise RuntimeError("未找到「定时发布」开关")
        await page.wait_for_timeout(2500)

        # 6. 填定时日期+时间
        day, hm = sched_time.split(" ")
        date_input = page.locator("input.arco-picker-start-time")
        await date_input.nth(0).fill(day)
        await date_input.nth(0).press("Enter")
        await page.wait_for_timeout(800)
        time_input = page.locator("input.arco-picker-start-time")
        await time_input.nth(1).fill(hm)
        await time_input.nth(1).press("Enter")
        await page.wait_for_timeout(800)

        # 校验填值
        v0 = await date_input.nth(0).input_value()
        v1 = await time_input.nth(1).input_value()
        if v0 != day or v1 != hm:
            raise RuntimeError(f"定时时间未填成功: 日期={v0} 时间={v1}, 期望 {sched_time}")

        # 6.5 选「是否使用AI = 否」(发布前必选, 实测不选会拦截发布)
        ai_ok = await page.evaluate("""() => {
          const labels=[...document.querySelectorAll('.arco-radio')];
          for(const l of labels){
            const t=(l.innerText||'').trim();
            if(t==='否'){
              const inp=l.querySelector('input[type=radio]');
              if(!inp || !inp.checked) l.click();
              return true;
            }
          }
          return false;
        }""")
        if not ai_ok:
            raise RuntimeError("未找到「是否使用AI」选项")
        await page.wait_for_timeout(1500)

        # 7. 确认发布 (button:has-text + force, 实测合成click无效)
        cbtn = page.locator("button:has-text('确认发布')")
        if await cbtn.count() < 1:
            raise RuntimeError("未找到「确认发布」按钮")
        await cbtn.last.click(timeout=10000, force=True)
        await page.wait_for_timeout(5000)

        # 7.5 番茄改版: 点外层确认发布后弹出「发布设置」modal, 其内部是独立表单
        #     (AI 未选/定时关/时间空), 需在 modal 内重新设置后再点一次确认发布.
        modal = page.locator(".arco-modal:visible")
        if await modal.count() > 0:
            log("  · 检测到发布设置弹窗, 在弹窗内重新设置并确认")
            # 弹窗内选「是否使用AI = 否」
            await modal.locator(".arco-radio").filter(has_text="否").click()
            await page.wait_for_timeout(800)
            # 弹窗内开定时发布
            msw = modal.locator("button.arco-switch")
            if await msw.count():
                if await msw.get_attribute("aria-checked") != "true":
                    await msw.click()
            await page.wait_for_timeout(1500)
            # 弹窗内填定时日期+时间
            mdt = modal.locator("input.arco-picker-start-time")
            day, hm = sched_time.split(" ")
            await mdt.nth(0).fill(day)
            await mdt.nth(0).press("Enter")
            await page.wait_for_timeout(800)
            await mdt.nth(1).fill(hm)
            await mdt.nth(1).press("Enter")
            await page.wait_for_timeout(800)
            mv0 = await mdt.nth(0).input_value()
            mv1 = await mdt.nth(1).input_value()
            if mv0 != day or mv1 != hm:
                raise RuntimeError(f"弹窗内定时时间未填成功: 日期={mv0} 时间={mv1}, 期望 {sched_time}")
            # 弹窗内点「确认发布」
            mc = modal.locator("button:has-text('确认发布')")
            if await mc.count() < 1:
                raise RuntimeError("发布设置弹窗内未找到「确认发布」按钮")
            await mc.nth(await mc.count() - 1).click(timeout=10000)
            # 提交后番茄会用 arco-message 闪现错误提示(如"提交字数超出每日上限", 1-2秒即消失),
            # 需在提交后立即密集轮询捕获, 否则会漏掉.
            for _ in range(10):
                msgs = await page.evaluate("""() => {
                  const els=[...document.querySelectorAll('.arco-message, .arco-notification')];
                  return els.filter(m=>m.offsetWidth).map(m=>(m.innerText||'').trim());
                }""")
                for m in msgs:
                    if "提交字数超出每日上限" in m:
                        raise RuntimeError("提交字数超出每日上限")
                if "/chapter-manage" in page.url:
                    break
                await page.wait_for_timeout(500)
            await page.wait_for_timeout(8000)

        # 8. 轮询检测成功: 跳转章节管理页 或 出现成功提示
        ok = False
        for _ in range(12):
            if "/chapter-manage" in page.url:
                ok = True
                break
            body = await page.evaluate("document.body.innerText")
            if ("发布成功" in body or "提交成功" in body) and ("重试" not in body or "失败" not in body):
                ok = True
                break
            # 提交字数超出每日上限 -> 明确失败原因
            if "提交字数超出每日上限" in body:
                raise RuntimeError("提交字数超出每日上限")
            if "发布失败" in body or "操作失败" in body or "违规" in body:
                break
            await page.wait_for_timeout(3000)
        if ok:
            log(f"  ✓ 第{num}章发布成功 (定时 {sched_time})")
            return True
        body = await page.evaluate("document.body.innerText")
        # 定位失败原因附近文本
        for kw in ("失败", "违规", "抱歉", "无法", "重试"):
            i = body.find(kw)
            if i >= 0:
                log(f"  页面提示: ...{body[max(0,i-80):i+120]}...")
                break
        raise RuntimeError(f"第{num}章发布结果无法确认, 需人工查看番茄后台(URL={page.url})")
    finally:
        await page.close()


# ===== 主流程 =====

async def main():
    ap = argparse.ArgumentParser(description="发布小说章节到番茄(定时)")
    ap.add_argument("--dry-run", action="store_true", help="只打印待发清单+排期, 不发布")
    ap.add_argument("--limit", type=int, default=0, help="最多发布 N 章 (0=全部)")
    ap.add_argument("--daily-limit", type=int, default=0, help="单次运行最多发布 N 章 (0=不限, 用于规避番茄每日字数上限)")
    ap.add_argument("--start", type=int, default=0, help="从第 N 章开始")
    ap.add_argument("--skip-first", type=int, default=0, help="跳过前 N 个待发章节")
    args = ap.parse_args()

    # 1. 后端 token
    token = get_backend_token()
    if not token:
        log("✗ 未找到有效的后台 token. 请先登录 http://127.0.0.1:3001 后台再重试.")
        sys.exit(1)
    log("✓ 后台 token 获取成功")

    # 2. 拉后台章节
    chapters = fetch_all_chapters(token)
    log(f"✓ 后台共 {len(chapters)} 章")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        page = await browser.contexts[0].new_page()
        try:
            # 3. 读番茄已发布最大章号
            fanqie_max = await get_fanqie_max_chapter(page)
            log(f"✓ 番茄已发布到第 {fanqie_max} 章")
            # 4. 补标后台章节(番茄已发布但后台未标已发, 如第7章)
            for c in chapters:
                if c["chapterNum"] <= fanqie_max and c.get("status") != 2:
                    if mark_published(token, c["id"]):
                        log(f"  ⇢ 补标后台第{c['chapterNum']}章《{c['title']}》为已发布")
            # 5. 待发清单
            prog = load_progress()
            pending = pick_backend_chapters(chapters, fanqie_max)
            if args.start:
                pending = [c for c in pending if c["chapterNum"] >= args.start]
            if args.skip_first:
                pending = pending[args.skip_first:]
            if not pending:
                log("没有待发布章节")
                return

            # 6. 排期 (从 fanqie_max 所在自动节奏组起点起全部章节, 已排章占槽; 今天12点已过则顺延明天)
            #    自动节奏: 第8章起每3章一天 (8,9,10 -> 今天; 11,12,13 -> 明天 ...)
            now = datetime.now()
            today_12_ok = now.replace(hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0) > now
            auto_start = max(fanqie_max - 2, 8)
            all_nums = [c["chapterNum"] for c in chapters if c["chapterNum"] >= auto_start]
            sched = build_schedule(all_nums, today_12_ok)
            save_fanqie_state(chapters, fanqie_max, sched, prog)

            log("===== 待发清单与排期 =====")
            for c in pending:
                log(f"  第{c['chapterNum']}章《{c['title']}》 -> {sched[c['chapterNum']]}")
            if args.limit:
                pending = pending[:args.limit]
                log(f"(本次仅发布前 {args.limit} 章)")
            if args.daily_limit:
                pending = pending[:args.daily_limit]
                log(f"(单次运行仅发布前 {args.daily_limit} 章, 规避每日字数上限)")
            if args.dry_run:
                log("[dry-run] 仅打印, 未发布")
                return

            # 7. 逐章发布
            for c in pending:
                num = c["chapterNum"]
                if num in prog.get("done", []):
                    log(f"  · 第{num}章已在进度中, 跳过")
                    continue
                log(f">>> 发布第{num}章《{c['title']}》 (定时 {sched[num]})")
                try:
                    await publish_one_chapter(browser, c, sched[num], token)
                except Exception as e:
                    msg = str(e)
                    # 番茄每日提交字数上限: 当天配额用尽, 属临时失败, 不标 failed, 剩余章节顺延明天重跑
                    if "提交字数超出每日上限" in msg:
                        log(f"✗ 第{num}章发布被拦截: {msg}")
                        log("   番茄单日提交字数已用尽, 剩余章节顺延到明天(0点后配额重置)再继续.")
                        # 清理当前章节的 failed 残留, 保证明天重试时它回到 pending
                        prog["failed"] = [f for f in prog.get("failed", []) if f["chapterNum"] != num]
                        prog.setdefault("quota_blocked", datetime.now().isoformat())
                        save_progress(prog)
                        save_fanqie_state(chapters, fanqie_max, sched, prog)
                        sys.exit(3)
                    log(f"✗ 第{num}章发布失败, 脚本暂停. 原因: {msg}")
                    prog.setdefault("failed", []).append({
                        "chapterNum": num, "error": msg, "time": datetime.now().isoformat()})
                    save_progress(prog)
                    save_fanqie_state(chapters, fanqie_max, sched, prog)
                    log("请人工处理(滑块/内容/后台状态)后重跑, 已完成的章节会跳过.")
                    sys.exit(2)
                # 标记后台已发
                if mark_published(token, c["id"]):
                    log(f"  ✓ 后台已标记第{num}章为已发布")
                else:
                    log(f"  ⚠ 第{num}章番茄已提交, 但后台标记失败, 需手动标记")
                prog.setdefault("done", []).append(num)
                save_progress(prog)
                save_fanqie_state(chapters, fanqie_max, sched, prog)
                time.sleep(3)
        finally:
            # 守卫页所有退出路径统一关闭(此前 dry-run/无待发/sys.exit 均泄漏, 在 9223 常驻 Chrome 上累积)
            try:
                await page.close()
            except Exception:
                pass
        log("===== 全部完成 =====")


if __name__ == "__main__":
    asyncio.run(main())
