#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上架前合规闸门自检. 跑法: automation/venv/bin/python test_pdd_compliance.py

每条断言都要能回答"生产代码改坏什么, 这条会红"。
规则库缺失必须报错而不是静默放行 —— 静默放行的闸门比没有闸门更危险,
因为它给出"已经检查过"的假象。
"""
import os
import tempfile

import pdd_compliance as G


def 断言规则库缺失时报错而不是空过():
    path = os.path.join(tempfile.mkdtemp(), "nope.json")
    try:
        G.load_rules(path)
    except FileNotFoundError as e:
        assert "compliance_rules.json" in str(e) or "规则库" in str(e), str(e)
        return
    raise AssertionError("规则库文件不存在却静默返回了 —— 闸门会假装检查过")


断言规则库缺失时报错而不是空过()


RULES = {
    "absolute_terms": ["最低价", "100%", "第一", "永久"],
    "medical_terms": ["美白", "祛斑", "医用"],
    "price_terms": ["原价", "清仓价"],
    "platform_red_line": {"taobao": ["官方", "正品保证"], "generic": ["授权"]},
    "trademark_hint": ["lv", "gucci", "克罗心"],
}


def 断言坏样本三类全命中():
    hits = G.hit_limited_words("全网最低价穿戴甲 100%持久 官方正品 美白祛斑 医用级", RULES)
    cats = {h["category"] for h in hits}
    assert {"绝对化用语", "医疗功效", "平台红线"} <= cats, cats
    words = {h["word"] for h in hits}
    assert {"最低价", "100%", "官方", "美白", "祛斑", "医用"} <= words, words


def 断言正常标题不误伤():
    for t in [
        "奈姿 手工穿戴甲甜蜜暴击立体手绘蝴蝶爱心猫眼款纯欲气质美甲贴",
        "纯手工光疗穿戴甲短方圆彩色星星甲美甲贴片短款可拆卸",
    ]:
        assert G.hit_limited_words(t, RULES) == [], t


def 断言英文商标词按ASCII词边界匹配():
    # involves 里就含子串 lv —— 纯子串匹配会把每个带英文单词的标题都误判成商标侵权
    assert G.hit_limited_words("involves 手工穿戴甲", RULES) == []
    assert {h["word"] for h in G.hit_limited_words("LV 同款穿戴甲", RULES)} == {"lv"}
    assert {h["word"] for h in G.hit_limited_words("这件 lv 同款", RULES)} == {"lv"}
    # 中文词不受词边界影响（克罗心 夹在中文里也要命中）
    assert "克罗心" in {h["word"] for h in G.hit_limited_words("磨砂克罗心穿戴甲", RULES)}


断言坏样本三类全命中()
断言正常标题不误伤()
断言英文商标词按ASCII词边界匹配()


def 断言重叠命中只算最长那条():
    # 规则库里 "最" 和 "最低价" 同时存在，子串匹配会各命中一次 ——
    # 一条标题被计成两处风险，存量体检的条数就会虚高（技能那边修过同一个 bug）
    rules = {"absolute_terms": ["最", "最低价", "全网最低价"], "platform_red_line": {}}
    hits = G.hit_limited_words("全网最低价穿戴甲", rules)
    assert [h["word"] for h in hits] == ["全网最低价"], hits


断言重叠命中只算最长那条()


REJ = [
    {"title": "【磨砂克罗心】甜酷气质风裸杏奶茶色磨砂钢珠克罗心穿戴甲"},
    {"title": "【陷阱克罗心】甜酷金粉猫眼碎钻星星贝壳克罗心蕾丝穿戴甲"},
    {"title": "【破碎之心】甜酷纯欲风爆闪水光猫眼金属克罗心贴钻穿戴甲"},
    {"title": "奈姿 纯手工光疗穿戴甲奶芙芙成品重复使用美甲贴片"},
    {"title": "奈姿 纯手工光疗穿戴甲猫眼奶芙芙成品使用美甲贴片"},
]
SALE = [  # 6 条真实在售标题（今天从 pdd_store_snapshot.json 里取的），用来压住通用词
    {"title": "奈姿 纯手工光疗穿戴甲春日花猫眼款重复使用美甲贴片可拆卸"},
    {"title": "奈姿 手工穿戴甲甜蜜暴击立体手绘蝴蝶爱心猫眼款纯欲气质美甲贴"},
    {"title": "纯手工光疗穿戴甲短方圆彩色星星甲美甲贴片短款可拆卸"},
    {"title": "奈姿 纯手工穿戴甲秋冬新款E060蜜雪法式蝴蝶猫眼款气质美甲贴片"},
    {"title": "奈姿 手工穿戴甲郁金香花园立体手绘郁金香猫眼款气质美甲贴片"},
    {"title": "纯手工光疗穿戴甲极简主义穿戴甲成品重复使用美甲贴片可拆卸"},
]


def 断言品牌词从驳回台账派生且不含供应商名():
    ranked = G.candidate_brand_words(REJ, SALE)
    brands = {w for w, _ in ranked}
    # 提名器的承诺是"真品牌词被某个候选覆盖"，不是"候选恰好等于品牌词"——
    # 4 字窗口(奶芙芙成)完全可能比 3 字根(奶芙芙)先入选，所以按"覆盖"断言。
    assert any("克罗心" in w for w in brands), brands
    assert any("奶芙芙" in w for w in brands), brands
    # 奈姿 是 1688 供应商名，在售里大量出现 —— 派生出来就会误杀 751 条货源
    assert not any("奈姿" in w for w in brands), brands
    # 清单要短到能人工看完，否则等于没提名
    assert len(brands) <= 8, brands


def 断言已拉黑的词不再重复提名():
    # 闸门每次跑都要从驳回台账提名；已经在 BRAND_WORDS 里的必须被剔掉，
    # 否则报告里永远挂着两条老词，新词会被淹掉
    got = G.derived_brands(REJ, SALE, known={"克罗心", "奶芙芙"})
    assert got == {"甜酷"}, got
    # 「芙芙成品」是「奶芙芙」的 4 字窗口切片，只查"是否包含"会漏 ——
    # 与已拉黑的词有 >=2 字公共片段的候选一律不再提名
    assert not any("芙芙" in w for w in got), got
    # 甜酷 与两个品牌词都没有公共片段，属于真正该给人看的新候选
    assert G.derived_brands(REJ, SALE, known=set()) >= {"甜酷"}


def 断言闸门拦住品牌词与极限词():
    ok, reasons = G.gate("甜酷气质风裸杏奶茶色磨砂钢珠克罗心穿戴甲", RULES, {"克罗心"})
    assert not ok and any("克罗心" in r for r in reasons), reasons
    ok2, reasons2 = G.gate("全网最低价穿戴甲", RULES, set())
    assert not ok2 and any("最低价" in r for r in reasons2), reasons2
    ok3, reasons3 = G.gate("奈姿 手工穿戴甲蝴蝶爱心猫眼款美甲贴", RULES, {"克罗心"})
    assert ok3 and reasons3 == [], reasons3


def 断言空规则库不许放行():
    # 规则被同步脚本写坏成空表时，闸门必须炸，不能"全部通过"
    try:
        G.gate("全网最低价穿戴甲", {}, {"克罗心"})
    except ValueError as e:
        assert "规则" in str(e), str(e)
        return
    raise AssertionError("空规则库被当成全部合规放行了")


断言品牌词从驳回台账派生且不含供应商名()
断言已拉黑的词不再重复提名()
断言闸门拦住品牌词与极限词()
断言空规则库不许放行()


import sync_compliance_rules as S  # noqa: E402


def 断言同步能报出新增与删除的词():
    d = S.diff_rules({"absolute_terms": ["最", "最低价"], "medical_terms": ["美白"]},
                     {"absolute_terms": ["最", "第一"], "medical_terms": ["美白"]})
    assert d["added"] == {"absolute_terms": ["第一"]}, d
    assert d["removed"] == {"absolute_terms": ["最低价"]}, d
    assert S.diff_rules({"absolute_terms": ["最"]}, {"absolute_terms": ["最"]})["changed"] is False


def 断言技能目录缺失时报错而不是静默():
    try:
        S.load_skill_rules(os.path.join(tempfile.mkdtemp(), "absent.json"))
    except FileNotFoundError as e:
        assert "技能" in str(e), str(e)
        return
    raise AssertionError("技能规则库不存在时静默返回了 —— 同步会把仓内规则覆盖成空表")


def 断言落盘文件带出处与时间():
    doc = S.build_doc({"absolute_terms": ["最"]}, "/skills/x/compliance-rules.json", "1.0.7")
    meta = doc["_meta"]
    assert meta["source"] == "/skills/x/compliance-rules.json"
    assert meta["skill_version"] == "1.0.7" and meta["synced_at"]
    assert meta["counts"] == {"absolute_terms": 1, "medical_terms": 0,
                              "price_terms": 0, "trademark_hint": 0}, meta
    assert doc["rules"]["absolute_terms"] == ["最"]


断言同步能报出新增与删除的词()
断言技能目录缺失时报错而不是静默()
断言落盘文件带出处与时间()
print("OK: pdd_compliance 断言通过")


def 断言队列过滤把不合规的挪到blocked并带原因():
    todo = [
        {"item_id": "a1", "title": "奈姿 手工穿戴甲蝴蝶爱心猫眼款美甲贴"},
        {"item_id": "b2", "title": "奈姿 纯手工光疗穿戴甲猫眼奶芙芙成品使用美甲贴片"},
        {"item_id": "c3", "title": "全网最低价穿戴甲"},
    ]
    kept, blocked = G.filter_by_gate(todo, RULES, {"克罗心", "奶芙芙"})
    assert [r["item_id"] for r in kept] == ["a1"], kept
    assert {b[0] for b in blocked} == {"b2", "c3"}, blocked
    why = dict((b[0], b[1]) for b in blocked)
    assert "品牌词:奶芙芙" in why["b2"], why
    assert any("最低价" in x for x in why["c3"]), why
    # 空标题不能当成"合规"放行 —— 上架时标题是必填项，空标题进队列本身就是脏数据
    kept2, blocked2 = G.filter_by_gate([{"item_id": "z", "title": "  "}], RULES, set())
    assert kept2 == [] and blocked2[0][0] == "z", (kept2, blocked2)


断言队列过滤把不合规的挪到blocked并带原因()
print("OK: pdd_compliance 断言通过")


import audit_pdd_catalog as A  # noqa: E402


def 断言体检汇总分开三类结论():
    on_sale = [
        {"goods_id": "1", "title": "奈姿 手工穿戴甲蝴蝶爱心猫眼款美甲贴", "price": "85.0"},
        {"goods_id": "2", "title": "克罗心风格穿戴甲", "price": "60.0"},
        {"goods_id": "3", "title": "全网最低价穿戴甲", "price": "42.5"},
    ]
    r = A.summarize(on_sale, RULES, {"克罗心"}, ref_factor=1.5, has_sales_data=False)
    assert r["total"] == 3
    assert [x["goods_id"] for x in r["title_hits"]] == ["2", "3"], r["title_hits"]
    assert any("克罗心" in x for x in r["title_hits"][0]["reasons"])
    assert any("最低价" in x for x in r["title_hits"][1]["reasons"])
    # 划线价：没有成交数据时，全部按倍数生成的参考价都算"无依据"
    assert r["ref_price"]["no_basis"] == 3, r["ref_price"]
    assert r["ref_price"]["factor"] == 1.5
    # 有成交数据时不该再报无依据（否则报告会永远红着）
    assert A.summarize(on_sale, RULES, {"克罗心"}, 1.5, has_sales_data=True)["ref_price"]["no_basis"] == 0


断言体检汇总分开三类结论()
print("OK: pdd_compliance 断言通过")


def 断言命中要带上下文供人工复核():
    # 真实误报样本：欧美白法式 → 子串里凑出「美白」。判据不该放宽（放过真功效宣称更贵），
    # 但报告必须带上下文，否则复核的人看到"医疗功效:美白"会以为标题真写了美白。
    hits = G.hit_limited_words("【冰透月光花】欧美白法式奶茶色渐变手工雕花穿戴甲", RULES)
    assert [h["word"] for h in hits] == ["美白"], hits
    assert "欧美白法式" in hits[0]["context"], hits[0]
    ok, reasons = G.gate("【冰透月光花】欧美白法式奶茶色渐变手工雕花穿戴甲", RULES, set())
    assert not ok and "欧美白法式" in reasons[0], reasons


断言命中要带上下文供人工复核()
print("OK: pdd_compliance 断言通过")


import collect_1688_imgs as I  # noqa: E402


def 断言原图还原与去重():
    # 1688 CDN 同一张图有多个尺寸后缀，必须归一到原图再去重，否则 3 个 URL 存成 3 张同样的图
    same = ["https://cbu01.alicdn.com/img/ibank/x/abc.jpg_.webp",
            "https://cbu01.alicdn.com/img/ibank/x/abc.jpg",
            "https://cbu01.alicdn.com/img/ibank/x/abc.jpg_310x310.jpg"]
    assert len({I.normalize_url(u) for u in same}) == 1, [I.normalize_url(u) for u in same]
    assert I.normalize_url("https://cbu01.alicdn.com/img/ibank/x/abc.jpg_50x50.jpg") == "https://cbu01.alicdn.com/img/ibank/x/abc.jpg"


def 断言挑图过滤图标并按序取主图():
    cands = ["https://cbu01.alicdn.com/img/ibank/x/a.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/logo_30x30.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/b.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/c.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/d.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/e.jpg",
             "https://cbu01.alicdn.com/img/ibank/x/f.jpg"]
    main, detail = I.pick_images(cands, max_main=5)
    assert main[:3] == ["https://cbu01.alicdn.com/img/ibank/x/a.jpg",
                        "https://cbu01.alicdn.com/img/ibank/x/b.jpg",
                        "https://cbu01.alicdn.com/img/ibank/x/c.jpg"], main
    assert len(main) == 5 and detail == ["https://cbu01.alicdn.com/img/ibank/x/f.jpg"], (main, detail)
    assert not any("logo" in u for u in main + detail)
    # 非 alicdn 的图（icon/统计图）一律不要
    assert I.pick_images(["https://example.com/track.gif"]) == ([], [])


断言原图还原与去重()
断言挑图过滤图标并按序取主图()
print("OK: collect_1688_imgs 断言通过")
