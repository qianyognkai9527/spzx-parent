#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量导入小说章节到 db_spzx.novel_chapter (幂等 upsert by novel_id+chapter_num)."""
import argparse
import json
import sys
from datetime import datetime

import pymysql

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
MIN_WORDS = 2800


def main():
    ap = argparse.ArgumentParser(description="小说章节批量导入")
    ap.add_argument("--novel-id", type=int, default=1)
    ap.add_argument("--file", required=True, help="JSONL 路径, 每行 {chapterNum,title,content}")
    ap.add_argument("--update-outline", help="可选: 回写 novel.outline 的 markdown 文本")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()

    chapters = []
    with open(args.file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chapters.append(json.loads(line))

    print(f"读取 {len(chapters)} 章")
    under = [c for c in chapters if len(c.get("content", "")) < MIN_WORDS]
    if under:
        for c in under:
            print(f"  [警告] 第{c['chapterNum']}章《{c.get('title','')}》{len(c['content'])}字 < {MIN_WORDS}")
        if not args.dry_run:
            print(f"存在低于{MIN_WORDS}字的章节, 中止导入(先修正)")
            sys.exit(1)

    if args.dry_run:
        print("[dry-run] 共", len(chapters), "章, 全部达标")
        return

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inserted = updated = 0
    for c in chapters:
        num = int(c["chapterNum"])
        title = c["title"]
        content = c["content"]
        wc = len(content)
        cur.execute(
            "SELECT id FROM novel_chapter WHERE novel_id=%s AND chapter_num=%s AND is_deleted=0",
            (args.novel_id, num),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE novel_chapter SET title=%s, content=%s, word_count=%s, is_modified=1, update_time=%s WHERE id=%s",
                (title, content, wc, now, row[0]),
            )
            updated += 1
        else:
            cur.execute(
                "INSERT INTO novel_chapter (novel_id, chapter_num, title, content, word_count, status, is_modified, create_time, update_time) "
                "VALUES (%s,%s,%s,%s,%s,0,0,%s,%s)",
                (args.novel_id, num, title, content, wc, now, now),
            )
            inserted += 1

    if args.update_outline:
        cur.execute(
            "UPDATE novel SET outline=%s, update_time=%s WHERE id=%s",
            (args.update_outline, now, args.novel_id),
        )
        print("大纲已回写")

    conn.commit()
    cur.close()
    conn.close()
    print(f"完成: 新增 {inserted}, 更新 {updated}")


if __name__ == "__main__":
    main()
