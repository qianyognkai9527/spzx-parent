"""视觉评分: 下载 source_product 头图, 按 清晰度/背景干净/色彩丰富(模特场景近似) 评分, 更新 visual_score(0-100)。
用法: python assess_visual.py [limit]"""
import sys
import io
import time
import pymysql
import requests
import numpy as np
from PIL import Image

DB = dict(host="127.0.0.1", user="root", password="root123456", database="db_spzx", port=3306)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def clarity_score(gray):
    """清晰度: 灰度梯度(近似 Laplacian)方差, 越高越清晰"""
    gx = np.gradient(gray, axis=1)
    gy = np.gradient(gray, axis=0)
    lap_var = np.var(gx**2 + gy**2)
    return 1.0 / (1.0 + 300.0 / (lap_var + 1e-6))


def clean_score(rgb):
    """背景干净度: 四角区域颜色标准差, 越小越干净"""
    h, w = rgb.shape[:2]
    c = 6
    ch, cw = h // c, w // c
    corners = [
        rgb[:ch, :cw], rgb[:ch, -cw:],
        rgb[-ch:, :cw], rgb[-ch:, -cw:],
    ]
    avg_std = float(np.mean([cr.std() for cr in corners]))
    return max(0.0, min(1.0, 1.0 - avg_std / 70.0))


def colorful_score(hsv):
    """色彩丰富度(近似模特/场景图优先): 饱和度均值高 = 有模特/场景/多色商品"""
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


def main(limit=200):
    if "--id" in sys.argv:
        idx = sys.argv.index("--id")
        source_id = int(sys.argv[idx + 1])
        conn = pymysql.connect(**DB)
        cur = conn.cursor()
        cur.execute("SELECT id, head_img_url FROM source_product WHERE id=%s", (source_id,))
        row = cur.fetchone()
        if not row:
            print(f"ERROR: source_product id={source_id} not found")
            sys.exit(1)
        rid, url = row
        try:
            r = requests.get(url, headers=UA, timeout=12)
            if r.status_code != 200:
                print(f"ERROR: download failed status={r.status_code}")
                sys.exit(1)
            score, detail = assess_bytes(r.content)
            if score is None:
                print(f"ERROR: too small {detail}")
                sys.exit(1)
            cur.execute("UPDATE source_product SET visual_score=%s WHERE id=%s", (score, rid))
            conn.commit()
            print(f"SCORE:{score}")
        finally:
            cur.close()
            conn.close()
        return

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, source_product_code, head_img_url FROM source_product "
        "WHERE head_img_url IS NOT NULL AND head_img_url != '' AND visual_score IS NULL LIMIT %s",
        (limit,),
    )
    rows = cur.fetchall()
    print(f"待评估 {len(rows)} 条")
    ok = fail = 0
    for rid, code, url in rows:
        try:
            r = requests.get(url, headers=UA, timeout=12)
            if r.status_code != 200:
                fail += 1
                continue
            score, detail = assess_bytes(r.content)
            if score is None:
                fail += 1
                continue
            cur.execute("UPDATE source_product SET visual_score=%s WHERE id=%s", (score, rid))
            conn.commit()
            ok += 1
            if ok <= 10:
                print(f"  #{rid} {code} score={score} {detail}")
        except Exception:
            fail += 1
        time.sleep(0.3)
    print(f"完成: 评分 {ok} 条, 失败 {fail} 条")
    cur.close()
    conn.close()


if __name__ == "__main__":
    if "--id" in sys.argv:
        main(0)
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
