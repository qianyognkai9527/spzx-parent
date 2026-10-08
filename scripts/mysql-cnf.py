#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建库参数文件 —— macOS 会清 /tmp，这份文件隔几天就没了。

口令只从 application-dev.yml 读，只写进 600 权限的文件，不出现在命令行、不回显。
同时写两份：/tmp/spzx_my.cnf（mysql 命令行用，AGENTS.md 里记的就是这个路径）
和 ~/.spzx/db.cnf（重启还在，automation 脚本经 dbconf.py 读它）。

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
LOCAL = YML.parent / "application-local.yml"
# 口令现在住在这里，dev.yml 里只剩 ${SPRING_DATASOURCE_PASSWORD:}
ENV_KEY = "SPRING_DATASOURCE_PASSWORD"
OUT = pathlib.Path(os.environ.get("SPZX_MYSQL_CNF", "/tmp/spzx_my.cnf"))
# 库参数在仓库外的常驻位置；dbconf.py 的搜索顺序里它排在 /tmp 之前
STABLE = pathlib.Path(os.path.expanduser("~/.spzx/db.cnf"))


def write_cnf(target, body):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)


def resolve_password(text):
    """按 环境变量 → application-local.yml → dev.yml 明文 的顺序找口令。
    留最后一条是为了老检出（口令还在 dev.yml 的时期）不至于突然生成不出来。"""
    if os.environ.get(ENV_KEY):
        return os.environ[ENV_KEY], "环境变量 " + ENV_KEY
    if LOCAL.exists():
        hit = re.search(r"datasource:\s*\n\s*password:\s*['\"]?(\S+)", LOCAL.read_text(encoding="utf-8"))
        if hit:
            return hit.group(1), LOCAL.name
    hit = re.search(r"password:\s*['\"]?(\S+)", text)
    return (hit.group(1), YML.name) if hit else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="写完顺手连一次，只报通/不通")
    args = ap.parse_args()

    text = YML.read_text(encoding="utf-8")
    url = re.search(r"jdbc:mysql://([^:/\s]+):(\d+)/(\w+)", text)
    user = re.search(r"username:\s*['\"]?(\S+)", text)
    pwd, where = resolve_password(text)
    if not (url and user and pwd):
        print("!! 拿不全 url/username/password（依次试过：环境变量 %s、%s、%s）"
              % (ENV_KEY, LOCAL.name, YML.name), file=sys.stderr)
        return 1
    print("口令取自 %s" % where)
    host, port, db = url.groups()
    # default-character-set 必须写死：这台机器的客户端默认 latin1，带中文的 SQL 不指定就双重编码
    body = ("[client]\nhost=%s\nport=%s\nuser=%s\npassword=%s\ndatabase=%s\n"
            "default-character-set=utf8mb4\n" % (host, port, user.group(1), pwd, db))
    targets = [OUT]
    if STABLE.resolve() != OUT.resolve():
        targets.append(STABLE)
    for target in targets:
        write_cnf(target, body)
        print("已写 %s（%s:%s/%s，%o 权限）" % (target, host, port, db,
                                              stat.S_IMODE(target.stat().st_mode)))

    if args.test:
        mysql = os.environ.get("SPZX_MYSQL_BIN", "/usr/local/mysql/bin/mysql")
        r = subprocess.run([mysql, "--defaults-extra-file=%s" % OUT, "-N", "-e", "select 1"],
                           capture_output=True, text=True)
        print("连接：通" if r.returncode == 0 else "连接：不通 —— %s" % r.stderr.strip()[:120])
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
