#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 /tmp/spzx_my.cnf —— macOS 会清 /tmp，这个文件隔几天就没了。

口令只从 application-dev.yml 读，只写进 600 权限的临时文件，不出现在命令行、不回显。
用法：python3 scripts/mysql-cnf.py            # 生成
      python3 scripts/mysql-cnf.py --test     # 生成后连一次，只报"通/不通"
"""
import argparse
import os
import pathlib
import re
import stat
import subprocess
import sys

YML = pathlib.Path(__file__).resolve().parent.parent / "spzx-manager/src/main/resources/application-dev.yml"
OUT = pathlib.Path(os.environ.get("SPZX_MYSQL_CNF", "/tmp/spzx_my.cnf"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="写完顺手连一次，只报通/不通")
    args = ap.parse_args()

    text = YML.read_text(encoding="utf-8")
    url = re.search(r"jdbc:mysql://([^:/\s]+):(\d+)/(\w+)", text)
    user = re.search(r"username:\s*['\"]?(\S+)", text)
    pwd = re.search(r"password:\s*['\"]?(\S+)", text)
    if not (url and user and pwd):
        print("!! 没从 %s 里同时解析出 url/username/password" % YML, file=sys.stderr)
        return 1
    host, port, db = url.groups()
    # default-character-set 必须写死：这台机器的客户端默认 latin1，带中文的 SQL 不指定就双重编码
    OUT.write_text("[client]\nhost=%s\nport=%s\nuser=%s\npassword=%s\ndatabase=%s\n"
                   "default-character-set=utf8mb4\n" % (host, port, user.group(1), pwd.group(1), db),
                   encoding="utf-8")
    OUT.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print("已写 %s（%s:%s/%s，%o 权限）" % (OUT, host, port, db, stat.S_IMODE(OUT.stat().st_mode)))

    if args.test:
        mysql = os.environ.get("SPZX_MYSQL_BIN", "/usr/local/mysql/bin/mysql")
        r = subprocess.run([mysql, "--defaults-extra-file=%s" % OUT, "-N", "-e", "select 1"],
                           capture_output=True, text=True)
        print("连接：通" if r.returncode == 0 else "连接：不通 —— %s" % r.stderr.strip()[:120])
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
