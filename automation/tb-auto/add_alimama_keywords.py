#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_alimama_keywords.py — 给阿里妈妈「关键词推广」智能计划(自定义智能最大化收割)单元批量新增关键词。

两种来源，各一次独立添加（本计划走系统智能出价，不设关键词出价）：
  ① AI选词     ：抽屉默认 tab（kr_fill_by_item）。切走 tab 再切回，防读缓存。
  ② 趋势机会词 ：「关键词推荐」tab 下的子项（kr_new_mta）。

选词（确定性规则，逐词可解释）：
  - 搜索指数 >= --min-index（默认 1000）
  - 必须含「商品名」：从该单元**商品标题**抽出的类目名词（外套/皮草/外衣/大衣…）；只有修饰词无商品名词的剔除（如「皮毛一体」）
  - 属性不冲突：标题声明的领型/长度维度，命中**同维度不同值**的剔除（如标题「立领」→ 剔「圆领/翻领/V领/连帽」）
  - 剔除含「的/了/吗/呢」等虚词的怪词
  - 排序：搜索指数降序（并列时市场点击率、市场点击转化率降序），取前 --top（默认 50）
  - 去重：对单元已有词、以及本轮两来源之间去重（忽略空格）

写入：直接 POST /bidword/add.json（不需要点 50 个勾选框；payload 与页面一致：
  {campaignId,adgroupId,word,bidPrice:1,matchScope:4,recReason:null}）。csrfId/loginPointId 从页面请求里现取。

跑法：
  automation/venv/bin/python add_alimama_keywords.py --campaign-id 83949710619 --dry-run --limit-units 1
  automation/venv/bin/python add_alimama_keywords.py --campaign-id 83949710619 --apply --gap 4
续跑：默认读 --report，已 ok 的「单元+来源」跳过。--adgroup-id 只跑指定单元。
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(BASE, "add_keywords_report.json")

CAMPAIGN_URL = ("https://one.alimama.com/index.html#!/manage/search-detail"
                "?mx_bizCode=onebpSearch&bizCode=onebpSearch&campaignId={cid}"
                "&tab=&startTime={d}&endTime={d}")
UNIT_URL = CAMPAIGN_URL + "&adgroupId={aid}"

# ---------------- 选词词典 ----------------

# 商品品类「家族」：词必须落在该单元标题所属家族，且不得落在别的家族
# （如标题=皮草外套 → 家族 coat：可留「毛领大衣」「派克服」；「皮草背心马甲」「女开衫」「毛衣」落在别的家族 → 剔）
GARMENT_FAMILIES = {
    "sleep": ["睡衣", "睡裙", "睡袍", "家居服", "家居裤"],
    "coat": ["外套", "外衣", "大衣", "夹克", "棉服", "羽绒服", "羽绒", "披风",
             "斗篷", "派克", "风衣", "袄", "呢子", "上衣", "皮草", "西装"],
    "sweater": ["毛衣", "针织衫", "开衫", "卫衣", "打底衫", "背心", "马甲"],
    "dress": ["连衣裙"],
    "skirt": ["半身裙", "短裙", "长裙", "百褶裙", "A字裙", "a字裙", "伞裙",
              "裙子", "裙"],
    "pants": ["裤"],
    "suit": ["套装"],
}

# 家族判定优先级：专精家族在前（word_family 最长名词平手时先者胜）。
# 睡衣 > 连衣裙 > 半身裙系：睡裙归 sleep 不归 skirt、连衣裙归 dress 不归 skirt。
FAMILY_PRIORITY = ["sleep", "dress", "skirt", "sweater", "coat", "pants", "suit"]

# 全局显式排除：含这些子串的词一律不选（家族规则覆盖不到的近形误伤）
EXCLUDE_SUBSTR = ["裤袜", "袜裤"]

# 季节薄厚维度（2026-10-17 用户要求：薄款链接不吃秋冬/加绒加厚/XX绒词，双向对称）。
# 暖边含裸「绒」子串——珊瑚绒/法兰绒/金貂绒/海岛绒/摇粒绒/天鹅绒/貂绒…全命中；
# 标题判边在 is_relevant 内部做：暖>薄，「四季/通用」=中性不设限。
SEASON_WARM = ["秋冬", "冬季", "冬天", "冬装", "冬款", "秋季", "秋款", "秋装", "深秋",
               "加绒", "加厚", "夹棉", "保暖", "绒", "毛毛", "貂", "羊羔毛"]
SEASON_THIN = ["夏季", "夏天", "夏款", "夏装", "薄款", "轻薄", "冰丝", "雪纺",
               "清凉", "透气", "短袖", "无袖"]
SEASON_ALL = ["四季", "春夏秋冬", "通用"]

# 领型维度：最长优先匹配（大翻领 先于 翻领）
COLLARS = ["大翻领", "翻领", "立领", "圆领", "V领", "v领", "方领", "连帽",
           "高领", "一字领", "娃娃领", "堆堆领", "棒球领", "西装领", "衬衫领",
           "海军领", "polo领", "连帽领", "无领", "吊带"]
# 长度维度：最长优先（中长款 先于 长款、短款）
LENGTHS = ["超短款", "中长款", "短款", "长款", "中款"]
# 材质维度（默认不参与剔除，--material-filter 打开）
MATERIALS = ["水貂", "貂毛", "狐狸毛", "兔毛", "獭兔毛", "羊羔毛", "羊毛", "貉子毛",
             "羽绒", "摇粒绒", "羊绒", "毛呢", "针织", "棉", "牛仔", "珊瑚绒",
             "法兰绒", "金貂绒", "海岛绒", "丝绒"]
BAD_CHARS = ["的", "了", "吗", "呢", "吧"]


def norm(w):
    return re.sub(r"\s+", "", w or "")


def pick_dim(title, terms):
    """从 title 里取第一个命中的维度词（按 terms 顺序，最长优先）。"""
    for t in terms:
        if t in title:
            return t
    return None


def dims_in(word, terms):
    found = []
    rest = word
    for t in terms:
        if t in rest:
            found.append(t)
            rest = rest.replace(t, "\x00" * len(t))
    return found


def title_family(title):
    """标题所属商品家族（命中维度词最多者；默认 coat）。"""
    best, bestn = "coat", 0
    for fam in FAMILY_PRIORITY:
        n = sum(1 for t in GARMENT_FAMILIES[fam] if t in title)
        if n > bestn:
            bestn, best = n, fam
    return best


def accepted_terms(title):
    fam = title_family(title)
    return GARMENT_FAMILIES[fam], fam


def word_family(word):
    """词所属家族：最长匹配名词优先（睡裙→sleep 而非 skirt；牛仔外套→coat）。
    平手按 FAMILY_PRIORITY 专精优先。无任何家族名词返回 None。"""
    best, bestlen = None, 0
    for fam in FAMILY_PRIORITY:
        for t in GARMENT_FAMILIES[fam]:
            if t in word and len(t) > bestlen:
                best, bestlen = fam, len(t)
    return best


def season_side(text):
    """标题/词的季节薄厚边：'warm' / 'thin' / None（中性）。
    特异性优先：暖>薄>中性——「加绒加厚…四季通用」是暖款（卖的就是加厚变体），
    「四季/通用/无信号」都算中性不设限。"""
    if not text:
        return None
    if any(s in text for s in SEASON_WARM):
        return "warm"
    if any(s in text for s in SEASON_THIN):
        return "thin"
    return None


def is_relevant(word, title, accepted, fam, t_collar, t_length, t_mats, material_filter):
    """返回 (ok, reason)。"""
    w = word.strip()
    if len(w) < 2:
        return False, "too_short"
    # 虚词剔除前先掩掉材质名词：「毛呢外套」的呢是呢子不是语气词（旧规则误杀，2026-10-17 修）
    w_bad = w
    for m in MATERIALS + ["呢子"]:
        w_bad = w_bad.replace(m, "\x00" * len(m))
    if any(c in w_bad for c in BAD_CHARS):
        return False, "bad_char"
    if any(s in w for s in EXCLUDE_SUBSTR):
        return False, "excluded"
    wf = word_family(w)
    if wf != fam:
        # 无家族名词（no_noun）或落别的家族（如 半身裙单元遇到 连衣裙）
        return False, f"family:{wf or 'none'}!={fam}"
    # 季节薄厚冲突（标题在调用方已传入）：暖标题剔薄边词，薄标题剔暖边词
    t_side = season_side(title)
    if t_side == "warm":
        for s in SEASON_THIN:
            if s in w:
                return False, f"season:{s}!={t_side}"
    elif t_side == "thin":
        for s in SEASON_WARM:
            if s in w:
                return False, f"season:{s}!={t_side}"
    # 领型冲突
    if t_collar:
        for c in dims_in(w, COLLARS):
            if c != t_collar:
                return False, f"collar:{c}!={t_collar}"
    # 长度冲突
    if t_length:
        for l in dims_in(w, LENGTHS):
            if l != t_length:
                return False, f"length:{l}!={t_length}"
    # 材质冲突（可选）
    if material_filter and t_mats:
        for m in dims_in(w, MATERIALS):
            if m not in t_mats:
                return False, f"material:{m}"
    return True, "ok"


def select_words(cands, title, accepted, fam, t_collar, t_length, t_mats, material_filter,
                 min_index, top, exclude):
    """cands: API list(原始 dict)。返回 (picked[list(dict)], dropped[list([word,reason])])。"""
    seen = set(exclude)
    scored = []
    dropped = []
    for c in cands:
        w = (c.get("word") or "").strip()
        if not w:
            continue
        idx = c.get("searchIndex") or 0
        try:
            idx = int(idx)
        except Exception:
            idx = 0
        if idx < min_index:
            continue
        if norm(w) in seen:
            continue
        ok, reason = is_relevant(w, title, accepted, fam, t_collar, t_length, t_mats, material_filter)
        if not ok:
            dropped.append([w, reason])
            continue
        scored.append((idx, c.get("marketClickRate") or 0.0,
                       c.get("marketClickConversionRate") or 0.0, c))
    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    picked = []
    for idx, _ctr, _cvr, c in scored:
        w = (c.get("word") or "").strip()
        if norm(w) in seen:
            continue
        seen.add(norm(w))
        picked.append({"word": w, "searchIndex": idx,
                       "marketClickRate": _ctr, "marketClickConversionRate": _cvr,
                       "competitionIndex": c.get("competitionIndex")})
        if len(picked) >= top:
            break
    return picked, dropped


# ---------------- 页面交互 ----------------

def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


async def get_units(page, campaign_id, day, logf):
    """从计划概览页捕获 findPage 请求并重放 pageSize=200，拿全部单元（含分页），
    返回 [{adgroupId, title}]（title 取 adgroupName）。"""
    tpl = {}
    caps = []

    async def on_resp(r):
        if "adgroup/horizontal/findPage.json" not in r.url:
            return
        try:
            post = json.loads(r.request.post_data or "{}")
        except Exception:
            post = {}
        if not tpl and post.get("pageSize", 0) >= 20:
            tpl["url"] = r.url
            tpl["body"] = post
        try:
            j = await r.json()
        except Exception:
            return
        lst = ((j.get("data") or {}).get("list")) or []
        if lst:
            caps.append(lst)

    page.on("response", lambda r: asyncio.create_task(on_resp(r)))
    await page.goto(CAMPAIGN_URL.format(cid=campaign_id, d=day),
                    wait_until="domcontentloaded", timeout=60000)
    for _ in range(20):
        await asyncio.sleep(1.5)
        if caps and tpl:
            break

    rows = max(caps, key=len) if caps else []
    if tpl:
        body = dict(tpl["body"])
        body["pageSize"] = 200
        body["offset"] = 0
        try:
            res = await page.evaluate("""async ([u,b]) => fetch(u,{method:'POST',
                headers:{'content-type':'application/json'},body:JSON.stringify(b),credentials:'include'})
                .then(r=>r.text())""", [tpl["url"], body])
            j = json.loads(res)
            lst = ((j.get("data") or {}).get("list")) or []
            if len(lst) > len(rows):
                rows = lst
        except Exception as e:
            logf(f"重放 findPage 失败: {str(e)[:70]}")
    out, seen = [], set()
    for a in rows:
        aid = str(a.get("adgroupId") or "")
        if aid and aid != "None" and aid not in seen:
            seen.add(aid)
            out.append({"adgroupId": aid, "title": (a.get("adgroupName") or "").strip()})
    return out


async def goto_unit(page, campaign_id, adgroup_id, day, logf):
    await page.goto(UNIT_URL.format(cid=campaign_id, aid=adgroup_id, d=day),
                    wait_until="domcontentloaded", timeout=60000)
    for _ in range(40):
        await asyncio.sleep(1)
        if await page.evaluate(r"""() => !!document.querySelector('span[mx-click*="addBidword"]')"""):
            return True
    return False


async def existing_words(page):
    return await page.evaluate(r"""() => {
      const out=[]; const seen=new Set();
      document.querySelectorAll('tr.keyword-item').forEach(tr=>{
        const a=tr.querySelector('a[href*="traffic-analysis"]');
        const w=a?(a.innerText||'').replace(/\s+/g,' ').trim():'';
        if(w && !seen.has(w)){seen.add(w);out.push(w);} });
      return out; }""")


async def read_keyword_rows(page):
    """读单元页现有关键词行 → [{id, word}]（去重，只保留有词的）。"""
    return await page.evaluate(r"""() => {
      const out=[]; const seen=new Set();
      document.querySelectorAll('tr.keyword-item').forEach(tr=>{
        const id=tr.getAttribute('data-keyword-id');
        const a=tr.querySelector('a[href*="traffic-analysis"]');
        const w=a?(a.innerText||'').replace(/\s+/g,' ').trim():'';
        if(id && w && !seen.has(id)){seen.add(id);out.push({id:id,word:w});} });
      return out; }""")


async def delete_ids(page, cid, aid, ids, tok, logf):
    """按 bidwordIdList 批量删除（每批 50）。返回 (ok, 删除数, 备注)。"""
    if not ids:
        return True, 0, "无"
    total = 0
    for i in range(0, len(ids), 50):
        batch = [int(x) for x in ids[i:i + 50]]
        res = await page.evaluate(r"""(a) => { const [tok,cid,aid,batch]=a;
          const body={bizCode:'onebpSearch',csrfId:tok.csrfId,loginPointId:tok.loginPointId,
            campaignId:cid,adgroupId:aid,bidwordIdList:batch};
          return fetch('/bidword/delete.json',{method:'POST',headers:{'content-type':'application/json'},
            credentials:'include',body:JSON.stringify(body)}).then(r=>r.json()).then(j=>{
              const info=j.info||{}; return {ok:info.ok!==false, err:info.message||null,
                count:(j.data&&j.data.count)||0}; }).catch(e=>({ok:false,err:String(e),count:0})); }""",
                                    [tok, cid, aid, batch])
        if not res.get("ok"):
            return False, total, str(res.get("err"))
        total += res.get("count", 0)
    return True, total, "ok"


async def open_drawer(page):
    return await page.evaluate(r"""() => {
      const e=document.querySelector('span[mx-click*="addBidword"]');
      if(!e) return false; e.scrollIntoView({block:'center'}); e.click(); return true; }""")


async def click_tab(page, label):
    return await page.evaluate(r"""(lab) => {
      const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
      const a=[...document.querySelectorAll('a[mx-click*="magix-portsB"]')]
        .filter(e=>e.offsetParent!==null && t(e).startsWith(lab));
      if(!a.length) return false; a[0].click(); return true; }""", label)


async def click_sub(page, label):
    return await page.evaluate(r"""(lab) => {
      const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
      const e=[...document.querySelectorAll('*')]
        .filter(x=>x.offsetParent!==null && t(x)===lab)
        .sort((a,b)=>b.querySelectorAll('*').length-a.querySelectorAll('*').length)[0];
      if(!e) return false; e.click(); return true; }""", label)


# ---------------- 主流程 ----------------

def load_report(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "items": []}


def save_report(path, rep):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def find_item(rep, aid, method):
    for it in rep["items"]:
        if it.get("adgroupId") == aid and it.get("method") == method:
            return it
    return None


async def add_words(page, cid, aid, words, tok, logf):
    payload = {"bizCode": "onebpSearch", "csrfId": tok.get("csrfId"),
               "loginPointId": tok.get("loginPointId"), "bidwordList": []}
    for w in words:
        payload["bidwordList"].append({"campaignId": cid, "adgroupId": aid, "word": w,
                                       "bidPrice": 1, "matchScope": 4, "recReason": None})
    res = await page.evaluate(r"""(p) => fetch('/bidword/add.json',
        {method:'POST', headers:{'content-type':'application/json'}, credentials:'include',
         body: JSON.stringify(p)}).then(r=>r.json()).then(j=>{
           const info=j.info||{};
           return {ok: info.ok!==false, err: info.message||info.errorMsg||null,
                   count: (j.data&&j.data.count)||0};
         }).catch(e=>({ok:false, err:String(e), count:0}))""", payload)
    if not res.get("ok"):
        return False, str(res.get("err"))
    return True, f"count={res.get('count')}"


async def run(args):
    day = date.today().isoformat()
    rep = load_report(args.report)
    SC = 9222
    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    processed = 0

    # 网络状态
    STORE = {}          # type -> list
    STAMP = {}          # type -> ts
    TOK = {"csrfId": None, "loginPointId": None}

    def on_req(r):
        u = r.url
        if "csrfId=" in u and not TOK["csrfId"]:
            m = re.search(r"csrfId=([^&]+)", u)
            if m:
                TOK["csrfId"] = m.group(1)
        if r.post_data and '"csrfId"' in r.post_data:
            try:
                d = json.loads(r.post_data)
                if d.get("csrfId"):
                    TOK["csrfId"] = d["csrfId"]
                if d.get("loginPointId"):
                    TOK["loginPointId"] = d["loginPointId"]
            except Exception:
                pass

    async def on_resp(r):
        if "kr/list.json" not in r.url:
            return
        try:
            d = json.loads(await r.text(), strict=False)
        except Exception:
            return
        ptype = ((d.get("data") or {}).get("type")) or None
        lst = (d.get("data") or {}).get("list")
        if not isinstance(lst, list):
            return
        # 从 POST 拿 type（响应里不一定有）
        tp = ptype
        try:
            pd = json.loads(r.request.post_data or "{}")
            tp = pd.get("type") or pd.get("selectedKeywordType") or tp
        except Exception:
            pass
        if tp:
            STORE[tp] = lst
            STAMP[tp] = time.time()

    page = next((p for p in ctx.pages if "alimama.com" in p.url), None)
    if page is None:
        page = await ctx.new_page()
    for p in list(ctx.pages):
        if p is not page:
            try:
                await p.close()
            except Exception:
                pass
    page.on("request", on_req)
    page.on("response", lambda r: asyncio.create_task(on_resp(r)))

    try:
        units = await get_units(page, args.campaign_id, day, log)
        if not units:
            log("!! 没读到单元列表（登录态掉了？）")
            return 2
        if args.adgroup_id:
            want = set(args.adgroup_id.split(","))
            units = [u for u in units if u["adgroupId"] in want]
        log(f"计划 {args.campaign_id} | 单元 {len(units)} 个 | {'DRY-RUN' if args.dry_run else 'APPLY'} "
            f"| min_index={args.min_index} top={args.top}")

        for ui, u in enumerate(units, 1):
            if args.limit_units and ui > args.limit_units:
                break
            aid, title = u["adgroupId"], u["title"]
            todo = [m for m in ("ai", "mta")
                    if not (not args.force and (find_item(rep, aid, m) or {}).get("status") == "ok")]
            if not todo:
                log(f"[{ui}/{len(units)}] {aid} 已全 ok，跳过")
                continue
            log(f"[{ui}/{len(units)}] {aid} | {title[:30]} | 待办 {todo}")

            if not await goto_unit(page, args.campaign_id, aid, day, log):
                log("   !! 单元页未就绪，跳过")
                continue
            await asyncio.sleep(1)

            # 读出旧词（先不删；若两来源都选不出新词则保留旧词，避免把单元清空）
            rows = await read_keyword_rows(page) if args.delete_old else []
            deleted = [r["word"] for r in rows]

            exist = await existing_words(page)
            accepted, fam = accepted_terms(title)
            t_collar = pick_dim(title, COLLARS)
            t_length = pick_dim(title, LENGTHS)
            t_mats = dims_in(title, MATERIALS)
            log(f"   属性: family={fam} collar={t_collar} length={t_length} material={t_mats} "
                f"| 已有词 {len(exist)}")

            opened = await open_drawer(page)
            if not opened:
                log("   !! 打开抽屉失败")
                continue
            await asyncio.sleep(6)

            exclude = {norm(w) for w in exist}
            plans = {}   # method -> (picked, dropped)

            # ---- ① AI选词 ----
            if "ai" in todo:
                await click_tab(page, "关键词推荐")      # 先切走
                await asyncio.sleep(2)
                t0 = time.time()
                await click_tab(page, "AI选词")           # 再切回（防缓存）
                ai = await _wait_type(STORE, STAMP, "kr_fill_by_item", t0, timeout=14) or []
                picked, dropped = _pick_with_fallback(ai, args, title, accepted, fam, t_collar,
                                                      t_length, t_mats, exclude)
                log(f"   AI选词: 候选 {len(ai)} → 入选 {len(picked)} / 剔除 {len(dropped)}")
                for p in picked[:60]:
                    log(f"      + {p['word']} (idx={p['searchIndex']} ctr={p['marketClickRate']} cvr={p['marketClickConversionRate']})")
                plans["ai"] = (picked, dropped)
                for p in picked:
                    exclude.add(norm(p["word"]))

            # ---- ② 趋势机会词 ----
            if "mta" in todo:
                t0 = time.time()
                await click_tab(page, "关键词推荐")
                await asyncio.sleep(2)
                await click_sub(page, "趋势机会词")
                mta = await _wait_type(STORE, STAMP, "kr_new_mta", t0, timeout=14) or []
                picked, dropped = _pick_with_fallback(mta, args, title, accepted, fam, t_collar,
                                                      t_length, t_mats, exclude)
                log(f"   趋势机会词: 候选 {len(mta)} → 入选 {len(picked)} / 剔除 {len(dropped)}")
                for p in picked[:60]:
                    log(f"      + {p['word']} (idx={p['searchIndex']} ctr={p['marketClickRate']} cvr={p['marketClickConversionRate']})")
                plans["mta"] = (picked, dropped)

            total = sum(len(v[0]) for v in plans.values())

            if args.dry_run:
                if args.delete_old:
                    log(f"   [dry] 将删除旧词 {len(rows)} 个: {deleted[:8]}")
                for m in ("ai", "mta"):
                    if m in plans:
                        await _record(rep, args, u, m, plans[m][0], plans[m][1],
                                      page, args.campaign_id, aid, TOK, exist, deleted, log)
                processed += 1
                await asyncio.sleep(args.gap)
                continue

            if total == 0:
                log("   ! 两来源均为 0 入选 → 保留旧词不删（避免把单元清空）")
                for m in ("ai", "mta"):
                    if m in plans:
                        await _record(rep, args, u, m, [], plans[m][1],
                                      page, args.campaign_id, aid, TOK, exist, [], log,
                                      skip_add=True, note="无入选词(保留旧词)")
                processed += 1
                await asyncio.sleep(args.gap)
                continue

            # 先加新词（成功后再删旧词；加失败则保留旧词，不制造空单元）
            added_any = False
            for m in ("ai", "mta"):
                if m in plans:
                    ok = await _record(rep, args, u, m, plans[m][0], plans[m][1],
                                       page, args.campaign_id, aid, TOK, exist, deleted, log)
                    added_any = added_any or bool(ok)

            # 删旧词（只删与本次新选不重合的旧词）
            if args.delete_old and rows and added_any:
                newset = {norm(p["word"]) for m in plans for p in plans[m][0]}
                del_rows = [r for r in rows if norm(r["word"]) not in newset]
                if del_rows:
                    okd, nd, note = await delete_ids(page, args.campaign_id, aid,
                                                     [r["id"] for r in del_rows], TOK, log)
                    log(f"   删除旧词 {nd}/{len(del_rows)} {'OK' if okd else 'FAIL:' + str(note)}")
                else:
                    log("   旧词与本次新选全部重合，无需删除")

            processed += 1
            await asyncio.sleep(args.gap)

        log(f"完成：处理 {processed} 个单元，报告 {args.report}")
        return 0
    finally:
        try:
            await b.close()
        except Exception:
            pass


async def _wait_type(STORE, STAMP, tname, t0, timeout=14):
    end = time.time() + timeout
    while time.time() < end:
        if STAMP.get(tname, 0) > t0:
            return STORE.get(tname)
        await asyncio.sleep(0.3)
    return STORE.get(tname)


async def _record(rep, args, u, method, picked, dropped, page, cid, aid, TOK, exist, deleted, logf,
                  skip_add=False, note=None):
    """记录一个来源的结果。返回是否「添加成功」（dry-run 恒 True）。"""
    words = [p["word"] for p in picked]
    item = {"adgroupId": aid, "title": u["title"], "method": method,
            "candidates": len(picked) + len(dropped), "picked": picked,
            "dropped": dropped[:200], "words": words,
            "existing": exist, "deleted": deleted, "ts": time.strftime("%F %T")}
    ok = True
    if args.dry_run:
        item["status"] = "dry"
    elif skip_add or not words:
        item["status"] = "ok"
        item["note"] = note or "无入选词"
    else:
        ok, msg = await add_words(page, cid, aid, words, TOK, logf)
        item["status"] = "ok" if ok else "fail"
        item["note"] = msg
        logf(f"      → 添加 {'OK' if ok else 'FAIL'}: {msg}")
    # 就地更新
    old = find_item(rep, aid, method)
    if old:
        old.update(item)
    else:
        rep["items"].append(item)
    save_report(args.report, rep)
    return ok


def _pick_with_fallback(cands, args, title, accepted, fam, t_collar, t_length, t_mats, exclude):
    """按 --min-index 选词；若一个都没选中，则用 --min-index-fallback 再选一次
    （仅放宽搜索指数下限，其余过滤规则不变）。"""
    picked, dropped = select_words(cands, title, accepted, fam, t_collar, t_length, t_mats,
                                   args.material_filter, args.min_index, args.top, exclude)
    if not picked and args.min_index_fallback < args.min_index:
        p2, d2 = select_words(cands, title, accepted, fam, t_collar, t_length, t_mats,
                              args.material_filter, args.min_index_fallback, args.top, exclude)
        if p2:
            return p2, d2
    return picked, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", default="83949710619")
    ap.add_argument("--adgroup-id", default=None, help="逗号分隔；不给=该计划所有单元")
    ap.add_argument("--min-index", type=int, default=1000, help="搜索指数下限")
    ap.add_argument("--min-index-fallback", type=int, default=200,
                    help="首个来源一个都选不出时，放宽到该指数下限再选一次（默认 200）")
    ap.add_argument("--top", type=int, default=50, help="每个来源最多取多少词")
    ap.add_argument("--gap", type=float, default=4.0, help="单元之间间隔秒数")
    ap.add_argument("--limit-units", type=int, default=0, help="本轮最多处理多少单元")
    ap.add_argument("--material-filter", action="store_true",
                    help="同时按材质维度剔冲突（如标题狐狸毛→剔兔毛词）；默认关")
    ap.add_argument("--delete-old", action="store_true",
                    help="加词前先删掉该单元现有的全部关键词（净结果=只保留本次新选词）")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--force", action="store_true", help="忽略历史 ok，整轮重算")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="只读+打印，不写入")
    g.add_argument("--apply", action="store_true", help="真正写入")
    a = ap.parse_args()
    if not a.apply:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
