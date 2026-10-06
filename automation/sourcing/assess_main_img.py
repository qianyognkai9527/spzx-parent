"""assess_main_img.py - 给平台商品主图(product_media)评分,离线下载图片评分
用法: python assess_main_img.py [limit]
复用 assess_visual 的算法(清晰度/背景干净/色彩丰富)
"""
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


def _alarm_handler(signum, frame):
    raise TimeoutError("download timeout")


def fetch_with_timeout(url, timeout=15):
    import signal
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout)
    try:
        return requests.get(url, headers=UA, timeout=(5, 8))
    finally:
        signal.alarm(0)


def main():
    if "--media-id" in sys.argv:
        idx = sys.argv.index("--media-id")
        media_id = int(sys.argv[idx + 1])
        conn = pymysql.connect(**DB)
        cur = conn.cursor()
        cur.execute("SELECT id, file_url FROM product_media WHERE id=%s", (media_id,))
        row = cur.fetchone()
        if not row:
            print(f"ERROR: product_media id={media_id} not found")
            sys.exit(1)
        mid, url = row
        try:
            r = fetch_with_timeout(url)
            if r.status_code != 200:
                print(f"ERROR: download failed status={r.status_code}")
                sys.exit(1)
            score, detail = assess_bytes(r.content)
            if score is None:
                print(f"ERROR: too small {detail}")
                sys.exit(1)
            # update_time 得显式写：这列是普通 datetime 没有 ON UPDATE，而质量分页的「分数截至」读 max(update_time)
            cur.execute("UPDATE product_media SET visual_score=%s, update_time=NOW() WHERE id=%s", (score, mid))
            conn.commit()
            print(f"SCORE:{score}")
        finally:
            cur.close()
            conn.close()
        return

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 999999
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("""SELECT id, file_url FROM product_media
        WHERE visual_score IS NULL AND file_url IS NOT NULL AND file_url != ''
        AND (file_url LIKE '%%alicdn%%' OR file_url LIKE '%%ecombdimg%%')
        LIMIT %s""", (limit,))
    rows = cur.fetchall()
    print(f"待评分: {len(rows)} 张主图", flush=True)
    ok = fail = 0
    for i, (mid, url) in enumerate(rows):
        try:
            r = fetch_with_timeout(url)
            if r.status_code != 200:
                fail += 1
                continue
            score, detail = assess_bytes(r.content)
            if score is None:
                fail += 1
                continue
            # update_time 得显式写：这列是普通 datetime 没有 ON UPDATE，而质量分页的「分数截至」读 max(update_time)
            cur.execute("UPDATE product_media SET visual_score=%s, update_time=NOW() WHERE id=%s", (score, mid))
            conn.commit()
            ok += 1
            if ok <= 15 or ok % 100 == 0:
                print(f"[{time.strftime('%H:%M:%S')}] {ok}/{len(rows)} score={score} {url[:50]}", flush=True)
        except Exception:
            fail += 1
            if fail <= 5:
                print(f"[{time.strftime('%H:%M:%S')}] fail#{fail} {url[:60]}", flush=True)
        time.sleep(0.1)
    print(f"完成: 评分 {ok} 张, 失败 {fail} 张", flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
