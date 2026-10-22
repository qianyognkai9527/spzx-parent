#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_alimama_word_rules.py — 选词家族规则单测（无网络）。

覆盖 2026-10-17 扩展：sleep 家族新增、skirt 从 dress 拆分、word_family 最长名词
优先（睡裙归睡衣不归半身裙）、牛仔跨家族归位、裤袜显式排除、吊带领型。
跑法: ./venv/bin/python tb-auto/test_alimama_word_rules.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import add_alimama_keywords as akw  # noqa: E402


def rel(word, fam, t_collar=None, t_length=None, t_mats=None, material_filter=False):
    return akw.is_relevant(word, "", akw.GARMENT_FAMILIES[fam], fam,
                           t_collar, t_length, t_mats, material_filter)


def test_title_family():
    assert akw.title_family("海岛绒睡衣女2025新款秋冬三件套可外穿加厚保暖豹纹感家居服") == "sleep"
    assert akw.title_family("瑰若加绒加厚法兰绒睡衣女吊带睡裙系带开襟家居服套装四季通用") == "sleep"
    assert akw.title_family("轻奢丝绒睡裙女大码带胸垫性感吊带家居服四季保暖睡袍") == "sleep"
    assert akw.title_family("高腰显瘦牛仔裤女秋冬") == "pants"
    assert akw.title_family("时尚百搭牛仔外套女春秋") == "coat"
    assert akw.title_family("法式复古半身裙女秋冬季") == "skirt"
    assert akw.title_family("性感吊带连衣裙女夏") == "dress"
    assert akw.title_family("白色羊羔毛皮草外套女加厚皮毛一体") == "coat"


def test_word_family():
    assert akw.word_family("吊带睡裙") == "sleep"      # 最长名词：睡裙(2) > 裙(1)
    assert akw.word_family("睡裙女冬") == "sleep"
    assert akw.word_family("珊瑚绒睡衣") == "sleep"
    assert akw.word_family("家居服套装") == "sleep"    # 家居服(3) > 套装(2)
    assert akw.word_family("连衣裙") == "dress"
    assert akw.word_family("碎花连衣裙") == "dress"
    assert akw.word_family("半身裙") == "skirt"
    assert akw.word_family("百褶裙") == "skirt"
    assert akw.word_family("牛仔裤") == "pants"
    assert akw.word_family("牛仔外套") == "coat"       # 外套(2) > 裤无
    assert akw.word_family("皮草外套") == "coat"
    assert akw.word_family("毛衣") == "sweater"
    assert akw.word_family("女冬新款") is None


def test_relevant_cross_family():
    # 半身裙单元：拒连衣裙，收半身裙系
    ok, why = rel("连衣裙", "skirt")
    assert not ok and "family:dress" in why, why
    ok, _ = rel("半身裙", "skirt"); assert ok
    ok, _ = rel("百褶裙", "skirt"); assert ok
    # 连衣裙单元：拒半身裙
    ok, why = rel("半身裙", "dress")
    assert not ok and "family:skirt" in why, why
    ok, _ = rel("碎花连衣裙", "dress"); assert ok
    # 睡衣单元：收睡裙/家居服，拒外套与半身裙
    ok, _ = rel("吊带睡裙", "sleep"); assert ok
    ok, _ = rel("珊瑚绒家居服", "sleep"); assert ok
    ok, why = rel("毛毛外套", "sleep")
    assert not ok and "family:coat" in why, why
    ok, why = rel("半身裙", "sleep")
    assert not ok and "family:skirt" in why, why
    # 牛仔裤单元：收牛仔裤，拒牛仔外套/裤袜
    ok, _ = rel("牛仔裤", "pants"); assert ok
    ok, _ = rel("高腰直筒牛仔裤女", "pants"); assert ok
    ok, why = rel("牛仔外套", "pants")
    assert not ok and "family:coat" in why, why
    ok, why = rel("光腿裤袜", "pants")
    assert not ok and why == "excluded", why
    # 外套单元：拒毛衣（原有互斥保持）
    ok, why = rel("毛衣", "coat")
    assert not ok and "family:sweater" in why, why
    ok, _ = rel("毛呢外套", "coat"); assert ok


def test_collar_and_material():
    # 吊带入领型维度后：吊带单元拒圆领
    ok, why = rel("圆领睡裙", "sleep", t_collar="吊带")
    assert not ok and "collar:圆领" in why, why
    ok, _ = rel("吊带睡裙", "sleep", t_collar="吊带"); assert ok
    # 材质过滤（可选开关）打开时：牛仔外套单元拒毛呢
    ok, why = rel("毛呢外套", "coat", t_mats=["牛仔"], material_filter=True)
    assert not ok and "material:毛呢" in why, why
    ok, _ = rel("牛仔外套", "coat", t_mats=["牛仔"], material_filter=True); assert ok
    # 默认关闭时不剔
    ok, _ = rel("毛呢外套", "coat", t_mats=["牛仔"], material_filter=False); assert ok


def test_season_side_and_conflict():
    # 判边：暖>薄优先（加绒加厚+四季通用 → 暖）；四季/无信号=中性
    assert akw.season_side("海岛绒睡衣女2025新款秋冬三件套可外穿加厚保暖豹纹感家居服") == "warm"
    assert akw.season_side("瑰若加绒加厚法兰绒睡衣女吊带睡裙系带开襟家居服套装四季通用") == "warm"
    assert akw.season_side("夏季薄款冰丝家居服女短袖") == "thin"
    assert akw.season_side("四季通用家居服女") is None
    assert akw.season_side("纯色套头家居服女") is None

    def rel_t(word, title, fam):
        return akw.is_relevant(word, title, akw.GARMENT_FAMILIES[fam], fam,
                               None, None, None, False)

    warm_t = "海岛绒睡衣女秋冬三件套加厚保暖家居服"
    thin_t = "夏季薄款冰丝家居服女短袖"
    neutral_t = "纯色套头家居服女"
    # 暖标题：剔薄边词（冰丝/薄款/夏季），收暖边与中性词
    ok, why = rel_t("冰丝睡裙", warm_t, "sleep")
    assert not ok and "season:冰丝" in why, why
    ok, why = rel_t("薄款家居服", warm_t, "sleep")
    assert not ok and "season:薄款" in why, why
    ok, why = rel_t("夏季睡衣", warm_t, "sleep")
    assert not ok and "season:夏季" in why, why
    ok, _ = rel_t("加厚睡衣", warm_t, "sleep"); assert ok
    ok, _ = rel_t("长款睡衣", warm_t, "sleep"); assert ok        # 中性词不剔
    ok, _ = rel_t("珊瑚绒家居服", warm_t, "sleep"); assert ok
    # 薄标题：剔暖边词（加厚/绒类/秋冬），收薄边与中性词
    ok, why = rel_t("加厚睡衣", thin_t, "sleep")
    assert not ok and "season:加厚" in why, why
    ok, why = rel_t("珊瑚绒睡衣", thin_t, "sleep")
    assert not ok and "season:绒" in why, why                   # 裸「绒」兜住各种绒
    ok, why = rel_t("冬季睡袍女", thin_t, "sleep")
    assert not ok and "season:冬季" in why, why
    ok, _ = rel_t("冰丝睡裙", thin_t, "sleep"); assert ok
    ok, _ = rel_t("睡衣女", thin_t, "sleep"); assert ok         # 中性词不剔
    # 中性标题：双向都不剔
    ok, _ = rel_t("加厚睡衣", neutral_t, "sleep"); assert ok
    ok, _ = rel_t("冰丝睡裙", neutral_t, "sleep"); assert ok
    # 牛仔短裤双向：薄标题拒加绒款，暖标题拒夏季款
    ok, why = rel_t("加绒牛仔短裤", "夏季薄款牛仔短裤女", "pants")
    assert not ok and "season:加绒" in why, why
    ok, why = rel_t("夏季牛仔短裤", "加绒牛仔短裤女秋冬", "pants")
    assert not ok and "season:夏季" in why, why
    ok, _ = rel_t("高腰牛仔短裤", "加绒牛仔短裤女秋冬", "pants"); assert ok


if __name__ == "__main__":
    test_title_family()
    test_word_family()
    test_relevant_cross_family()
    test_collar_and_material()
    test_season_side_and_conflict()
    print("all ok")
