"""generate_main_img_variants.py - 基于商品现有主图生成多套更优质主图变体
程序化变体(PIL), 无外部AI依赖。存 /Users/qyk9527/tb/headImges。

用法:
  python generate_main_img_variants.py --product-id X --platform-type 1|2 [--set N] [--test]
    --product-id  platform_product.id
    --platform-type 1=淘宝 2=抖音
    --set N  指定套号(默认取该商品最大set+1)
    --test   只处理img_pos=1一张, 不落库(验证用)

落库 product_media_variant, 每张生成后自动评分。打印 SET:N
"""
import sys
import os
import io
import time
import pymysql
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

DB = dict(host="127.0.0.1", user="root", password="root123456", database="db_spzx", port=3306)
OUT_DIR = "/Users/qyk9527/tb/headImges"
RULES = ["brighten", "bokeh", "crop", "dark", "warm"]


def clarity_score(gray):
    gx = np.gradient(gray, axis=1)
    gy = np.gradient(gray, axis=0)
    lap_var = np.var(gx**2 + gy**2)
    return 1.0 / (1.0 + 300.0 / (lap_var + 1e-6))


def clean_score(rgb):
    h, w = rgb.shape[:2]
    c = 6
    ch, cw = h // c, w // c
    corners = [rgb[:ch, :cw], rgb[:ch, -cw:], rgb[-ch:, :cw], rgb[-ch:, -cw:]]
    avg_std = float(np.mean([cr.std() for cr in corners]))
    return max(0.0, min(1.0, 1.0 - avg_std / 70.0))


def colorful_score(hsv):
    s = hsv[:, :, 1].astype(float)
    return float(np.mean(s) / 255.0)


def assess_bytes(data):
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    if w < 300 or h < 300:
        return None, {"size": f"{w}x{h}"}
    arr = np.asarray(img)
    gray = np.asarray(img.convert("L"), dtype=float)
    hsv = np.asarray(img.convert("HSV"))
    c = clarity_score(gray)
    cl = clean_score(arr)
    cf = colorful_score(hsv)
    score = (0.4 * c + 0.3 * cl + 0.3 * cf) * 100
    return round(score), {"clarity": round(c, 2), "clean": round(cl, 2), "colorful": round(cf, 2)}


def apply_variant(img, rule):
    """返回处理后的 PIL 图"""
    if rule == "brighten":
        return ImageEnhance.Brightness(img).enhance(1.2).convert("RGB")
    if rule == "bokeh":
        w, h = img.size
        blurred = img.filter(ImageFilter.GaussianBlur(10))
        center_rect = (int(w * 0.18), int(h * 0.18), int(w * 0.82), int(h * 0.82))
        mask = Image.new("L", (w, h), 0)
        draw = ImageDrawForMask(mask, center_rect)
        return Image.composite(img, blurred, mask)
    if rule == "crop":
        w, h = img.size
        cw, ch = int(w * 0.85), int(h * 0.85)
        left = (w - cw) // 2
        top = (h - ch) // 2
        return img.crop((left, top, left + cw, top + ch)).resize((w, h), Image.LANCZOS).convert("RGB")
    if rule == "dark":
        dark = ImageEnhance.Brightness(img).enhance(0.82).convert("RGB")
        r, g, b = dark.split()
        r = r.point(lambda p: int(p * 0.92))
        return Image.merge("RGB", (r, g, b)).convert("RGB")
    if rule == "warm":
        r, g, b = img.split()
        r = r.point(lambda p: int(min(255, p * 1.08)))
        b = b.point(lambda p: int(p * 0.94))
        return Image.merge("RGB", (r, g, b)).convert("RGB")
    return img.convert("RGB")


def ImageDrawForMask(mask, rect):
    """在 mask 上填充中心矩形为白色(255), 用纯PIL方式"""
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    d.rectangle(rect, fill=255)
    return mask


def load_source_images(cur, product_id, platform_type):
    """返回 {img_pos: (url or path, bytes)}"""
    cur.execute(
        "SELECT img_pos, file_url FROM product_media "
        "WHERE product_id=%s AND platform_type=%s AND img_pos IN (1,2,3,4,5) ORDER BY img_pos",
        (product_id, platform_type),
    )
    rows = cur.fetchall()
    out = {}
    for img_pos, url in rows:
        if not url:
            continue
        out[img_pos] = url
    return out


def get_next_set(cur, product_id):
    cur.execute("SELECT COALESCE(MAX(variant_set), 0) FROM product_media_variant WHERE product_id=%s", (product_id,))
    return int(cur.fetchone()[0] or 0) + 1


def save_variant(img, product_id, variant_set, img_pos, rule):
    """保存变体图, 返回本地路径 + 评分"""
    d = os.path.join(OUT_DIR, str(product_id), f"set{variant_set}")
    os.makedirs(d, exist_ok=True)
    fname = f"img{img_pos}_{rule}.jpg"
    fpath = os.path.join(d, fname)
    img.save(fpath, "JPEG", quality=92)
    with open(fpath, "rb") as f:
        data = f.read()
    score, _ = assess_bytes(data)
    return fpath, score


def main():
    args = sys.argv[1:]
    if "--product-id" not in args:
        print("用法: --product-id X --platform-type 1|2 [--set N] [--test]")
        sys.exit(1)
    product_id = int(args[args.index("--product-id") + 1])
    platform_type = int(args[args.index("--platform-type") + 1])
    test = "--test" in args
    variant_set = None
    if "--set" in args:
        variant_set = int(args[args.index("--set") + 1])

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    try:
        src = load_source_images(cur, product_id, platform_type)
        if not src:
            print("ERROR: 该商品没有原始主图(img_pos 1-5)")
            sys.exit(1)
        if variant_set is None:
            variant_set = get_next_set(cur, product_id)

        for img_pos in sorted(src):
            url = src[img_pos]
            # 下载原始主图
            import requests
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=(5, 8))
                if r.status_code != 200:
                    print(f"  img{img_pos}: 下载失败 status={r.status_code}")
                    continue
                orig = Image.open(io.BytesIO(r.content)).convert("RGB")
            except Exception as e:
                print(f"  img{img_pos}: 下载异常 {e}")
                continue

            for rule in RULES:
                variant_img = apply_variant(orig, rule)
                fpath, score = save_variant(variant_img, product_id, variant_set, img_pos, rule)
                if not test:
                    cur.execute(
                        "INSERT INTO product_media_variant "
                        "(product_id, platform_type, variant_set, img_pos, rule_name, file_url, visual_score, create_time) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())",
                        (product_id, platform_type, variant_set, img_pos, rule, fpath, score),
                    )
                    conn.commit()
                print(f"  img{img_pos} {rule}: score={score}")
            if test:
                break  # 只处理一张
        print(f"SET:{variant_set}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
