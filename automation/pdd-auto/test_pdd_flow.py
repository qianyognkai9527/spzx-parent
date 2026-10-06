#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""无人值守逻辑自检: 验证码隔离计数 + 驳回→品牌词候选抽取 + 驳回原因抽取.
跑法: automation/venv/bin/python test_pdd_flow.py

只测这三块纯逻辑 —— 主循环其余分支要动真实店铺才能验, 不适合放这儿。
record_captcha 对应 10-02 那次空转: 一件商品卡验证码 -> 整条队列退出重来 -> 同一件永远排队首,
4 轮下来在草稿箱留了两条同名草稿。
"""
import pdd_config as C
from create_pdd_product import record_captcha


def fresh():
    return {"done": [], "failed": {}, "skipped": []}


# 第一次卡住: 不隔离, 只是先跳过, 进度文件里不动 failed
p = fresh()
q, n = record_captcha(p, "966442252934", "验证码未通过[滑块]")
assert (q, n) == (False, 1)
assert p["failed"] == {}
assert p["captcha"]["966442252934"] == 1

# 第二次: 到隔离阈值, 落进 failed 并带上第几次, 下一轮不再排队
q, n = record_captcha(p, "966442252934", "验证码未通过[滑块]")
assert (q, n) == (True, 2)
assert "966442252934" in p["failed"]
assert p["failed"]["966442252934"].startswith("验证码隔离(第2次)")

# 阈值可配: 调高后同一件继续累加而不是立刻隔离
_orig = C.CAPTCHA_QUARANTINE_AFTER
try:
    C.CAPTCHA_QUARANTINE_AFTER = 5
    p2 = fresh()
    for i in range(1, 5):
        q, n = record_captcha(p2, "x", "m")
        assert (q, n) == (False, i), (i, q, n)
    assert record_captcha(p2, "x", "m") == (True, 5)
finally:
    C.CAPTCHA_QUARANTINE_AFTER = _orig

# 不同商品各自计数, 不能互相污染
p3 = fresh()
assert record_captcha(p3, "a", "m") == (False, 1)
assert record_captcha(p3, "b", "m") == (False, 1)
assert record_captcha(p3, "a", "m") == (True, 2)
assert p3["captcha"]["b"] == 1

# 老进度文件没有 captcha 键也要能跑(setdefault 兜住)
assert "captcha" not in fresh()
p4 = fresh()
record_captcha(p4, "c", "m")
assert p4["captcha"] == {"c": 1}

# ---- 品牌词候选抽取: 用 2026-10-05 店铺里真实的 5 条驳回 + 在售标题当夹具 ----
from sync_pdd_store import candidate_brand_words  # noqa: E402

REJECTED = [
    {"title": "【磨砂克罗心】甜酷气质风裸杏奶茶色磨砂钢珠克罗心穿戴甲"},
    {"title": "【陷阱克罗心】甜酷金粉猫眼碎钻星星贝壳克罗心蕾丝穿戴甲"},
    {"title": "【破碎之心】甜酷纯欲风爆闪水光猫眼金属克罗心贴钻穿戴甲"},
    {"title": "奈姿 纯手工光疗穿戴甲奶芙芙成品重复使用美甲贴片"},
]
ON_SALE = [
    {"title": "奈姿 纯手工穿戴甲秋冬新款E060蜜雪法式蝴蝶猫眼款气质美甲贴片"},
    {"title": "奈姿 手工穿戴甲甜蜜暴击立体手绘蝴蝶爱心猫眼款纯欲气质美甲贴"},
    {"title": "纯手工光疗穿戴甲短方圆彩色星星甲美甲贴片短款可拆卸"},
    {"title": "奈姿 手工穿戴甲郁金香花园立体手绘郁金香猫眼款气质美甲贴片"},
]
cands = dict(candidate_brand_words(REJECTED, ON_SALE))
# 克罗心在 3 条驳回里出现、在售里查无此词 -> 必须被提名
assert cands.get("克罗心") == 3, cands
# 子串不该再来一遍（罗心/克罗 的命中数与克罗心相同，会被母串吃掉）
assert not any(w in cands for w in ("罗心", "克罗", "心穿")), cands
# 奈姿 是供应商名且在在售里大量出现 -> 绝不能提名(提名了就等于把它当品牌词误杀)
assert not any("奈姿" in w for w in cands), [w for w in cands if "奈姿" in w]
# 通用词也不能混进来: 这些字串在售里都有
for generic in ("穿戴甲", "手工", "猫眼", "美甲贴片", "纯手工"):
    assert generic not in cands, generic
# 只命中 1 条驳回的词(奶芙芙)按 >=2 的门槛不会提名 —— 这是有意的保守, 单次驳回不足以定黑名单,
# 但要知道这个上限存在: 那类词得靠人补进 BRAND_WORDS(2026-10-05 就是手工补的)。
assert not any("奶芙芙" in w for w in cands)

# ---- 驳回原因抽取: 用 2026-10-05 从「已驳回」Tab 抓到的真实行文本当夹具 ----
from sync_pdd_store import reason_of  # noqa: E402

REAL_ROW = ("奈姿 纯手工光疗穿戴甲奶芙芙成品重复使用美甲贴片 | ID: 1011894607239 | 商品编码：-- | "
            "\t发布已驳回 | 驳回原因：为加强平台品牌商品管控，该商品需提交来源凭证。请您点击【申诉】按钮，"
            "上传该销售商品对应的进货凭证或品牌授权证明 | 主账号 | 发布 | 2026-10-01 15:15 | 查看 | 编辑 | 申诉")
r = reason_of({"raw": REAL_ROW})
assert r.startswith("驳回原因："), r[:40]
assert "品牌商品管控" in r and "来源凭证" in r
# 原因后面的操作列不能混进来
for junk in ("主账号", "删除草稿", "2026-10-01"):
    assert junk not in r, junk
# 没有驳回字样时不能崩，退回整行
assert reason_of({"raw": "标题 | ID: 1"}) == "标题 | ID: 1"

print("OK: record_captcha + candidate_brand_words + reason_of 全部断言通过")

# ---- 验证码等待自适应: 第 2 次不再盲等（它已注定被隔离，等 300s 是纯浪费）----
from create_pdd_product import captcha_wait_seconds  # noqa: E402

assert captcha_wait_seconds(1) == C.CAPTCHA_WAIT_SEC, "第 1 次仍要留人工救援的时间"
assert captcha_wait_seconds(2) == 0, "第 2 次直接隔离，不该再等"
assert captcha_wait_seconds(9) == 0
print("OK: captcha_wait_seconds 断言通过")

# ---- 事件等待原语: 固定 sleep 换成"条件成立就往下走" ----
import asyncio as _aio  # noqa: E402
from create_pdd_product import wait_until  # noqa: E402


class _FakePage:
    """假页面：按脚本依次返回 evaluate 结果，记录被问了几次。"""
    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0
    async def evaluate(self, _js):
        self.calls += 1
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


def 断言等条件成立就返回():
    p = _FakePage([False, False, True])
    got = _aio.run(wait_until(p, "js", timeout=2, step=0.01))
    assert got is True and p.calls == 3, (got, p.calls)
    # 第一次就问到了，不该再问第二次
    p2 = _FakePage([True])
    assert _aio.run(wait_until(p2, "js", timeout=2, step=0.01)) is True and p2.calls == 1


def 断言超时返回False而不是抛异常():
    p = _FakePage([False])
    got = _aio.run(wait_until(p, "js", timeout=0.05, step=0.01))
    assert got is False, got        # 超时=条件没等到，由调用方决定是回退等待还是判失败
    assert p.calls >= 2, p.calls    # 真的轮询了，不是问一次就放弃


def 断言条件抛异常不炸穿整个流程():
    class _Boom:
        async def evaluate(self, _js):
            raise RuntimeError("页面还没准备好")
    assert _aio.run(wait_until(_Boom(), "js", timeout=0.05, step=0.01)) is False


断言等条件成立就返回()
断言超时返回False而不是抛异常()
断言条件抛异常不炸穿整个流程()
print("OK: wait_until 断言通过")

# ---- 类目推荐等不到的真因: 标题还没落进输入框就按 Tab，推荐区整页不渲染 ----
from create_pdd_product import ensure_category_recommendations  # noqa: E402


class _RecoPage:
    """模拟：第 1 次填的标题被页面自己的异步逻辑清掉 -> Tab 白按；回读发现为空再填才好。"""

    class _KB:
        def __init__(self, outer):
            self.outer = outer

        async def press(self, _k):
            self.outer.tabs += 1

    def __init__(self):
        self.value = ""
        self.tabs = 0
        self.fills = 0
        self.keyboard = _RecoPage._KB(self)

    async def evaluate(self, js):
        if "查看更多推荐" in js:
            # 只有标题真的在框里、且按过 Tab，推荐才渲染
            return bool(self.value) and self.tabs >= 1
        if "querySelector" in js and "value" in js:
            return self.value
        return False

    async def fill(self, _sel, text):
        self.fills += 1
        # 第 1 次填进去会被页面异步清掉（实测现象），第 2 次才留住
        self.value = "" if self.fills == 1 else text


def 断言标题被清掉时重填再试():
    p = _RecoPage()
    ok = _aio.run(ensure_category_recommendations(p, "奈姿 手工穿戴甲猫眼款", timeout_each=1, log=None))
    assert ok is True, "重填一次就该等到推荐"
    assert p.fills >= 2, f"应该重填了，实际 fill 次数={p.fills}"


断言标题被清掉时重填再试()
print("OK: ensure_category_recommendations 断言通过")
