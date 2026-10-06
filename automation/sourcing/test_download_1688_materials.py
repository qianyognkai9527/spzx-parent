#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""download_1688_materials 纯函数单测: normalize_url / unique_imgs / clean_title / img_size。"""
import struct
import tempfile
import os

import download_1688_materials as D


def test_normalize():
    cases = {
        "https://cbu01.alicdn.com/img/ibank/a.jpg_310x310.jpg": "https://cbu01.alicdn.com/img/ibank/a.jpg",
        "https://cbu01.alicdn.com/img/ibank/a.jpg_.webp": "https://cbu01.alicdn.com/img/ibank/a.jpg",
        "https://cbu01.alicdn.com/img/ibank/a.png": "https://cbu01.alicdn.com/img/ibank/a.png",
        "https://cbu01.alicdn.com/img/ibank/a.jpg?x=1": "https://cbu01.alicdn.com/img/ibank/a.jpg",
        "https://cbu01.alicdn.com/img/ibank/a_100x100.jpg": "https://cbu01.alicdn.com/img/ibank/a.jpg",
    }
    for k, v in cases.items():
        got = D.normalize_url(k)
        assert got == v, f"{k} -> {got} != {v}"


def test_unique():
    cands = [
        "https://cbu01.alicdn.com/img/ibank/logo_abc.jpg",
        "https://other.com/a.jpg",
        "https://cbu01.alicdn.com/img/ibank/1.jpg_310x310.jpg",
        "https://cbu01.alicdn.com/img/ibank/1.jpg",          # 归一后与上重复
        "https://cbu01.alicdn.com/img/ibank/2.jpg",
        "https://cbu01.alicdn.com/img/ibank/qrcode.jpg",
    ]
    got = D.unique_imgs(cands, 10)
    assert got == [
        "https://cbu01.alicdn.com/img/ibank/1.jpg",
        "https://cbu01.alicdn.com/img/ibank/2.jpg",
    ], got


def test_title():
    assert D.clean_title("一只顾【奶油雪雪】穿戴甲-阿里巴巴") == "一只顾【奶油雪雪】穿戴甲"
    assert D.clean_title("a/b:c*d") == "a b c d"


def test_img_size_png():
    # 最小 PNG 头: 89 50 4E 47 0D 0A 1A 0A + IHDR(len=13,'IHDR',w,h,...)
    png = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
           + struct.pack(">II", 800, 600) + b"\x08\x02\x00\x00\x00" + b"\x00\x00\x00\x00")
    fd, p = tempfile.mkstemp(suffix=".png")
    try:
        os.write(fd, png); os.close(fd)
        assert D.img_size(p) == (800, 600), D.img_size(p)
    finally:
        os.remove(p)


if __name__ == "__main__":
    test_normalize()
    test_unique()
    test_title()
    test_img_size_png()
    print("PASS: download_1688_materials")
