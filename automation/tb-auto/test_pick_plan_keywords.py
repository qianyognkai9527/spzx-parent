#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pick_plan_keywords 纯函数单测（无网络，仓库惯例：python 直跑）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_plan_keywords import (bq, build_traffic_hash, upsert,  # noqa: E402
                                is_brand_word, filter_brand_words)


def test_bq_double_encodes():
    # 实测：流量解析 href 里词是双重 URL 编码
    assert bq("女皮草") == "%25E5%25A5%25B3%25E7%259A%25AE%25E8%258D%2589"


def test_build_traffic_hash():
    h = build_traffic_hash("狐狸毛外套", "83949710619", "83872915734")
    assert h.startswith("#!/insight/search/traffic-analysis/index?word=")
    assert "campaignId=83949710619" in h
    assert "adgroupId=83872915734" in h
    assert "bidwordId=" in h


def test_upsert_dedupes_by_unit_and_word():
    rep = {"items": []}
    upsert(rep, "1", "词a", {"adgroupId": "1", "word": "词a", "status": "dry"})
    upsert(rep, "1", "词a", {"adgroupId": "1", "word": "词a", "status": "ok"})
    upsert(rep, "2", "词a", {"adgroupId": "2", "word": "词a", "status": "dry"})
    assert len(rep["items"]) == 2
    assert rep["items"][0]["status"] == "ok"
    assert rep["items"][1]["adgroupId"] == "2"


def test_is_brand_word_and_filter():
    # 品牌词黑名单 / ≥2 连续英文字母 / 正常词不受影响（2026-10-17 琳琳皮草混入事件）
    assert is_brand_word("琳琳皮草")
    assert is_brand_word("cc皮草")
    assert is_brand_word("羽绒服鸭鸭")
    assert is_brand_word("波司登羽绒服")
    assert not is_brand_word("毛毛外套")
    assert not is_brand_word("妈妈羽绒服")
    assert not is_brand_word("T恤")          # 单字母不剔
    assert not is_brand_word("a字毛呢外套")
    assert not is_brand_word("皮草外套")
    keep, dropped = filter_brand_words(
        [{"word": w} for w in ("琳琳皮草", "皮草外套", "cc皮草")], [])
    assert [p["word"] for p in keep] == ["皮草外套"]
    assert [p["word"] for p in dropped] == ["琳琳皮草", "cc皮草"]
    # --brand-blocklist 追加生效
    keep2, _ = filter_brand_words([{"word": "某新品牌皮草"}], ["某新品牌"])
    assert keep2 == []


def test_word_roundtrip_via_hash():
    # word_from_hash（adjust 侧）应还原双重编码的词，含空格
    import adjust_alimama_bid as akb
    for w in ("皮草外套", "外套 女 羊羔毛", "羊羔绒外套女 中长款"):
        assert akb.word_from_hash("https://one.alimama.com/index.html" + build_traffic_hash(w)) == w


if __name__ == "__main__":
    test_bq_double_encodes()
    test_build_traffic_hash()
    test_upsert_dedupes_by_unit_and_word()
    test_is_brand_word_and_filter()
    test_word_roundtrip_via_hash()
    print("all ok")
