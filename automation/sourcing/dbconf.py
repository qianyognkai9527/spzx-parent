#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""库连接参数的唯一来源 —— 口令不再抄进脚本。

为什么要有它：automation 下 24 个脚本各自写着 host/user/明文口令，而这个仓库是推到 GitHub 的，
等于口令跟着代码一起走；AGENTS.md 自己规定"密钥/凭据放 application-local.yml，勿提交"。
现在统一读一份 600 权限、且**不在仓库里**的 cnf（由 `scripts/mysql-cnf.py` 从
application-dev.yml 生成）。

找文件的顺序：环境变量 `SPZX_MYSQL_CNF` → `~/.spzx/db.cnf`（重启还在）→ `/tmp/spzx_my.cnf`
（macOS 清 /tmp，所以它只是兼容旧用法）。都没有时抛的异常里直接写着重建命令。

`DB_CONFIG` 是惰性的：真正解包成关键字参数时才去读文件。cron_batch / cron_alert 的既有约定是
"连不上就吞掉异常继续跑，不许把 cron 链打挂"，模块导入期就抛会破坏这条约定。
"""
import os
import pathlib
from collections.abc import Mapping

SEARCH_PATHS = (
    os.path.expanduser("~/.spzx/db.cnf"),
    "/tmp/spzx_my.cnf",
)
# 这台机器的 mysql 客户端默认 latin1，带中文的 SQL 不显式指定就会双重编码
CHARSET = "utf8mb4"
DEFAULT_DB = "db_spzx"


def cnf_path():
    """当前能用上的那份参数文件；一份都没有时返回 None（由调用方决定报错还是静默降级）"""
    for p in (os.environ.get("SPZX_MYSQL_CNF"),) + SEARCH_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def read_cnf(path):
    """只认 [client] 段里的 key=value。不用 configparser：它会把键名转小写、
    还可能把口令里的 % 当插值，而这串字符是原样传给服务端的。"""
    out, section = {}, ""
    for raw in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section == "client" and "=" in line:
            key, value = line.split("=", 1)
            out[key.strip().lower()] = value.strip().strip("\"'")
    return out


def params():
    """pymysql.connect(**params()) 要的完整参数"""
    path = cnf_path()
    if not path:
        raise RuntimeError("找不到库参数文件（找过 %s）—— 生成：python3 scripts/mysql-cnf.py"
                           % " → ".join(SEARCH_PATHS))
    conf = read_cnf(path)
    missing = [k for k in ("host", "user", "password") if not conf.get(k)]
    if missing:
        raise RuntimeError("%s 的 [client] 段缺 %s —— 重跑：python3 scripts/mysql-cnf.py"
                           % (path, "/".join(missing)))
    try:
        port = int(conf.get("port") or 3306)
    except ValueError:
        raise RuntimeError("%s 里 port=%r 不是数字" % (path, conf.get("port")))
    return {
        "host": conf["host"],
        "port": port,
        "user": conf["user"],
        "password": conf["password"],
        "database": conf.get("database") or DEFAULT_DB,
        "charset": conf.get("default-character-set") or CHARSET,
    }


class LazyParams(Mapping):
    """解包时才读文件，让 22 处 `pymysql.connect(**DB_CONFIG)` 一行都不用改"""

    def __iter__(self):
        return iter(params())

    def __len__(self):
        return len(params())

    def __getitem__(self, key):
        return params()[key]

    def __repr__(self):
        # 绝不能把口令带进日志或 traceback
        return "<dbconf.LazyParams cnf=%s>" % (cnf_path() or "缺失")


DB_CONFIG = LazyParams()


def connect(**overrides):
    """给那些把参数直接摊在 connect(...) 里的脚本用"""
    import pymysql
    cfg = params()
    cfg.update(overrides)
    return pymysql.connect(**cfg)
