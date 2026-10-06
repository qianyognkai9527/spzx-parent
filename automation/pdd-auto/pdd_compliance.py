#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上架前合规闸门（纯函数）: 规则库加载、词命中、品牌词派生、单件商品判定.

规则库 `compliance_rules.json` 是从已装技能同步进仓的副本（同步见 sync_compliance_rules.py），
放仓内是为了仓库搬家/换机器时闸门仍然有效；技能目录本身不作为运行时依赖。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(BASE, "compliance_rules.json")

_CATEGORY_LABEL = {
    "absolute_terms": "绝对化用语",
    "medical_terms": "医疗功效",
    "price_terms": "价格表述",
    "trademark_hint": "疑似商标",
}
# 技能规则库里没有 pinduoduo 这一档；generic + taobao 是国内平台的并集口径
_PLATFORM_SOURCES = {
    "pinduoduo": ("generic", "taobao"),
    "taobao": ("generic", "taobao"),
    "douyin": ("generic", "taobao"),
}
_ASCII_EDGE = re.compile(r"[a-z0-9]")


def load_rules(path=None):
    """读规则库。文件缺失/损坏一律抛错 —— 静默返回空规则等于闸门形同不存在还宣称检查过。"""
    p = path or RULES
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"合规规则库不存在：{p}。跑 `python sync_compliance_rules.py` 从技能目录同步一份，"
            "不要改成缺省放行。")
    with open(p, encoding="utf-8") as f:
        doc = json.load(f)
    if not isinstance(doc.get("rules"), dict) or not doc["rules"]:
        raise ValueError(f"合规规则库 {p} 里没有 rules 内容，闸门拒绝以空规则放行。")
    return doc


def _iter_words(rules, platform):
    """展开成 (类别, 词)。规则库缺某一类就跳过那一类，不报错。"""
    for key, label in _CATEGORY_LABEL.items():
        for w in rules.get(key) or []:
            if w:
                yield label, w
    red = rules.get("platform_red_line") or {}
    for src in _PLATFORM_SOURCES.get(platform, ("generic",)):
        for w in red.get(src) or []:
            if w:
                yield "平台红线", w


def hit_limited_words(title, rules, platform="pinduoduo"):
    """标题命中的合规风险词 -> [{category, word, at, end}]。

    两条必要的严格性，都是为了让"命中"这件事经得起人工复核：
    - 纯 ASCII 词（lv/gucci…）按词边界匹配 —— 否则 involves 里的 lv 会把好标题批量误杀；
    - 重叠命中只留最长的一条 —— 否则「全网最低价」会被「最」「最低价」「全网最低价」各计一次，
      存量体检的风险条数会虚高到没法看。
    """
    t = (title or "").lower()
    found = []
    for label, word in _iter_words(rules, platform):
        w = word.lower()
        start = t.find(w)
        while start >= 0:
            ok = True
            if all(ord(c) < 128 for c in w):
                before = t[start - 1] if start > 0 else ""
                after = t[start + len(w)] if start + len(w) < len(t) else ""
                if _ASCII_EDGE.match(before) or _ASCII_EDGE.match(after):
                    ok = False
            if ok:
                # 带上上下文：中文没有词边界，"欧美白法式" 里会凑出「美白」这种误命中，
                # 报告里只写词名会让人以为标题真写了功效宣称，复核成本就差这几字符。
                found.append({"category": label, "word": word, "at": start, "end": start + len(w),
                              "context": t[max(0, start - 6):start + len(w) + 6]})
            start = t.find(w, start + 1)
    found.sort(key=lambda h: (h["at"], -(h["end"] - h["at"])))
    out, until = [], -1
    for h in found:
        if h["at"] < until:
            continue
        out.append(h)
        until = h["end"]
    return out


def candidate_brand_words(rejections, on_sale, min_hits=2, max_len=4):
    """从驳回标题里提名品牌词候选：只出现在驳回、在售里查无此词、命中 >= min_hits。

    反向条件用"在售里不存在"是因为驳回样本少、在售样本多：只看驳回里的高频词会把
    「穿戴甲/手工/猫眼」这类通用词全列出来；真品牌词的特征恰恰是只在被驳回那几条里出现。
    命中数相同的子串会被母串吃掉（克罗心 覆盖 罗心/克罗）。
    **提名 ≠ 拉黑**：结果只用于"跳过这一件"，转正进 BRAND_WORDS 要人确认 ——
    把供应商名 奈姿 误判成品牌词的代价是队列里 751 条货源。
    """
    sale_blob = " ".join(r.get("title", "") for r in on_sale)
    grams = {}
    for r in rejections:
        t = r.get("title", "")
        per = set()
        for n in range(2, max_len + 1):
            for i in range(len(t) - n + 1):
                w = t[i:i + n]
                if not ("一" <= w[0] <= "鿿"):
                    continue
                if any(c in "，。、【】()（）0123456789" for c in w):
                    continue
                if w in per or w in sale_blob:
                    continue
                per.add(w)
                grams[w] = grams.get(w, 0) + 1
    cand = [(w, n) for w, n in grams.items() if n >= min_hits]
    cand.sort(key=lambda x: (-x[1], -len(x[0]), x[0]))
    out = []
    for w, n in cand:
        if any(w in kept for kept, _ in out):
            continue
        out.append((w, n))
    return out


def _shares_run(a, b, n=2):
    """两个词是否有 >=n 字的公共片段。"""
    return any(a[i:i + n] in b for i in range(len(a) - n + 1))


def derived_brands(rejections, on_sale, min_hits=2, known=()):
    """闸门用的品牌词集合 = 提名出来、且尚未被拉黑的那批词。

    known(BRAND_WORDS) 命中的候选要剔掉：一个词只要已经在黑名单里，就不必再当"新提名"报一次，
    否则每次体检报告都挂着同样的老词，真正的新词会被淹掉。
    判据用"公共片段"而不是"包含"：「芙芙成品」是「奶芙芙」的 4 字窗口切片，
    两者互不包含，只查包含会把它当成新词反复报。
    """
    out = set()
    for w, _ in candidate_brand_words(rejections, on_sale, min_hits=min_hits):
        if any(k and (k in w or _shares_run(w, k)) for k in known):
            continue
        out.add(w)
    return out


def gate(title, rules, brands=()):
    """单件商品能不能提交 -> (ok, reasons)。

    只管"标题层面就能判定"的风险；划线价(参考价)不在这里拦 —— 那是经营决定，
    由 audit_pdd_catalog.py 出数，改不改由人拍。
    """
    known = any(rules.get(k) for k in _CATEGORY_LABEL) or bool(rules.get("platform_red_line"))
    if not known:
        raise ValueError("规则库里没有任何已知类别的词，闸门拒绝把「全部通过」当成合规。")
    t = title or ""
    reasons = [f"品牌词:{b}" for b in sorted(brands) if b and b in t]
    reasons += [f"{h['category']}:{h['word']}（…{h['context']}…）" for h in hit_limited_words(t, rules)]
    return (not reasons), reasons


def brands_for_publish(known, rejections, on_sale):
    """生效品牌词 = 手工黑名单 ∪ 台账提名（已拉黑的不重复报）。"""
    return set(known) | derived_brands(rejections, on_sale, known=set(known))


def filter_by_gate(todo, rules, brands=()):
    """把待提交队列分成 (放行, [(item_id, reasons)])。

    放在连浏览器之前跑：拦下来不占页面、不产生草稿、也不消耗风控额度。
    空标题算不合规 —— 标题是必填项，空标题进队列本身就是脏数据，让平台报错不如自己先拦。
    """
    kept, blocked = [], []
    for rec in todo:
        title = (rec.get("title") or "").strip()
        if not title:
            blocked.append((rec.get("item_id"), ["标题为空"]))
            continue
        ok, reasons = gate(title, rules, brands)
        if ok:
            kept.append(rec)
        else:
            blocked.append((rec.get("item_id"), reasons))
    return kept, blocked


def load_json_list(path, key=None):
    """读台账/快照这类可选数据文件：不存在就返回空，但把原因如实带回来给调用方打印。

    规则库(compliance_rules.json)不走这条路 —— 那个缺失必须报错；
    驳回台账和在售快照缺失只是"少了一批派生词"，手工黑名单仍然生效，不该拦住铺货。
    """
    if not os.path.exists(path):
        return [], f"{os.path.basename(path)} 不存在，本次不做台账派生提名"
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return [], f"{os.path.basename(path)} 读失败({type(e).__name__})，本次不做台账派生提名"
    rows = doc.get(key) if key else doc
    return (rows or []), None
