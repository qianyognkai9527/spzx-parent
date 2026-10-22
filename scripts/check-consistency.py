#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一致性门 —— 把 AGENTS.md 里三条"改一处必须改另一处"的口头约定做成可重跑的检查。

  A 调度：同一个作业"几点跑"一共有四份副本 —— crontab、~/Library/LaunchAgents 的
          plist、ingest_dataset.cron_expr、automation/sourcing/task-progress-config.json。
          2026-10-04 就是发现推广采集只有第一份有、后两份空着才补上的。
  B 契约：前端 src/api 声明的 (method, path) 必须在后端 controller 有能匹配上的端点。
  C 判据：异常流量判据在 DashboardMapper 与 ItemOpsMapper.xml 各一份 —— 这一条已由
          ItemOpsParamTest 逐字钉住，本门只断言"那条测试还在"，不重抄规则。
  D 销案：cron_alert.py 的每处调用必须带 --dataset 且指向注册表里的数据集 —— 没有它，
          后端拿不到"这个作业后来跑成了"的依据，提醒只会越积越多（顶栏 badge 永不回落）。
  E 凭据：代码与配置里不得出现库口令 —— Python 走 automation/sourcing/dbconf.py 读仓库外的
          600 文件，Java 走 gitignore 的 application-local.yml。历史交付台账里的明文不在射程内。

退出码：0 全过 / 1 有漂移 / 2 有一维根本没扫到（扫不到东西不等于没问题）。
先跑 --selftest 证明这些判据报得出红，再相信它报的绿。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
MYSQL_CNF = os.environ.get("SPZX_MYSQL_CNF", "/tmp/spzx_my.cnf")
MYSQL_BIN = os.environ.get("SPZX_MYSQL_BIN", "/usr/local/mysql/bin/mysql")
FRONTEND_CANDIDATES = [
    os.environ.get("SPZX_FRONTEND_SRC"),
    "/Users/qyk9527/webstormProject/spzx-admin",
]

# 覆盖面下限：低于这个数说明扫描面缩了（路径变了/目录没检出），这次的结论不可信
# crontab 下限 2026-10-19 由 5 调成 3：调度优化（spec schedule-optimization §3）把作业迁到
# LaunchAgent，crontab 只剩 task_stats(每小时) / sycm 12:35 / db_daily 04:30 三条活动行，
# 这是预期收窄（launchd 侧从 1 涨到 6 条），不是路径/目录没检出。再少就是真缩了。
# launchd 下限 2026-10-19 由 1 调成 4：调度优化把作业从 crontab 迁来，现有 6 个
# com.spzx.* Agent（daily-schedule / stock-refresh / stock-sync / onsale-scan / alimama-promo
# / db-backup），留 2 条容差——再少就是 plist 目录没检出，不是真缩了。
FLOOR = {"crontab": 3, "launchd": 4, "registry": 8, "progress_scheduled": 5,
         "frontend_urls": 150, "backend_routes": 150, "alert_callers": 14, "secret_scanned": 600}


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def norm_path(p):
    """两边统一：补前导斜杠，路径变量（后端 {id} / 前端 ${id}）都写成 {}"""
    p = re.sub(r"\$\{[^}]*\}", "{}", p)
    p = re.sub(r"\{[^{}]*\}", "{}", p)
    if not p.startswith("/"):
        p = "/" + p
    return re.sub(r"/{2,}", "/", p).rstrip("/") or "/"


def path_matches(fe, be):
    """路径变量两边都可能出现在任一侧：段数相同、逐段相等或有一侧是 {} 即算匹配"""
    a, b = fe.split("/"), be.split("/")
    if len(a) != len(b):
        return False
    return all(x == y or "{}" in (x, y) for x, y in zip(a, b))


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def hhmm_of(expr):
    """cron 表达式 / 中文时刻文本 → (时, 分)；拿不到返回 None"""
    m = re.search(r"(\d{1,2}):(\d{2})", expr or "")
    if m:
        return (int(m.group(1)), int(m.group(2)))
    parts = (expr or "").split()
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return (int(parts[1]), int(parts[0]))
    return None


# ---------------------------------------------------------------- A 调度
def cron_targets(cmd):
    """一行命令真正会跑到的脚本：命令里点名的 .py/.sh，加上被点名 shell 脚本内部的 .py。
    detect_alerts.py 这类作业是被 inventory_cron.sh 链式调用的，没有自己的 crontab 行。"""
    found = set(re.findall(r"([\w./\-]+\.(?:py|sh))", cmd))
    expanded = set(found)
    todo = [p for p in found if p.endswith(".sh")]
    while todo:
        rel = todo.pop()
        path = pathlib.Path(rel)
        if not path.exists():
            path = REPO / "automation" / "sourcing" / os.path.basename(rel)
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8", errors="ignore")
        for inner in set(re.findall(r"([\w./\-]+\.py)", body)):
            expanded.add(inner)
        for nested in set(re.findall(r"([\w./\-]+\.sh)", body)) - expanded:
            expanded.add(nested)
            todo.append(nested)
    return {os.path.basename(p) for p in expanded}


def read_crontab():
    out = []
    for line in sh(["crontab", "-l"]).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        out.append((" ".join(parts[:5]), parts[5]))
    return out


def read_launchd():
    out = []
    agents = pathlib.Path.home() / "Library" / "LaunchAgents"
    for plist in sorted(agents.glob("com.spzx.*.plist")):
        body = plist.read_text(encoding="utf-8", errors="ignore")
        args = re.findall(r"<string>([^<]+)</string>",
                          body.split("<key>ProgramArguments</key>")[-1].split("</array>")[0])
        hour = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", body)
        minute = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", body)
        expr = "%s %s * * *" % (minute.group(1) if minute else "0",
                                hour.group(1) if hour else "0")
        out.append((plist.name, expr, " ".join(args)))
    return out


def read_registry():
    """ingest_dataset 注册表（权威的那一份）：code → {cron, scripts, monitor}"""
    if not os.path.exists(MYSQL_CNF):
        raise RuntimeError("缺少 %s —— 检查 A 跑不了（重建方式见 AGENTS.md：从 application-dev.yml 生成，chmod 600）" % MYSQL_CNF)
    raw = sh([MYSQL_BIN, "--defaults-extra-file=" + MYSQL_CNF, "-N",
              "-e", "select code, ifnull(cron_expr,''), ifnull(writer,''), monitor from ingest_dataset"])
    rows = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        code, cron, writer, monitor = parts[:4]
        script = writer.split(":")[-1].strip()
        rows[code] = {"cron": cron,
                      "scripts": {os.path.basename(s) for s in re.findall(r"[\w./\-]+\.(?:py|sh)", script)},
                      "monitor": monitor == "1"}
    return rows


def read_progress_json():
    path = REPO / "automation" / "sourcing" / "task-progress-config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = {}
    for t in data.get("tasks", []):
        scripts = set()
        for s in ([t.get("script")] if t.get("script") else []) + (t.get("scripts") or []):
            scripts |= cron_targets(str(s))
        tasks[t.get("key")] = {"schedule": t.get("schedule"), "scripts": scripts,
                               "category": t.get("category")}
    return tasks


def check_schedules(crontab, launchd, registry, progress, report):
    """四份副本对齐：注册表里每个监控项，机器上得真有人在跑、且时刻三处一致"""
    machine = {}
    for expr, cmd in crontab:
        for base in cron_targets(cmd):
            machine[base] = (expr, "crontab")
    for name, expr, cmd in launchd:
        for base in cron_targets(cmd):
            machine[base] = (expr, "launchd:" + name.replace(".plist", ""))
    card = {}
    for key, t in progress.items():
        for base in t["scripts"]:
            card[base] = (t["schedule"], key)

    for code, row in sorted(registry.items()):
        if not row["monitor"]:
            continue
        base = sorted(row["scripts"])[0] if row["scripts"] else ""
        if not row["cron"]:
            report.fail("A", "%s 是监控项却没写 cron_expr —— 看板的「应跑时间」无从计算" % code)
            continue
        if not base:
            report.fail("A", "%s 是监控项但 writer 里没解析出脚本名，无法核对机器上的调度" % code)
            continue
        hits = [base] + sorted(row["scripts"])
        found = next(((expr, src) for b in dict.fromkeys(hits) if b in machine for expr, src in [machine[b]]), None)
        if not found:
            report.fail("A", "注册表说 %s 该由 %s 跑（%s），但 crontab/LaunchAgent 里都没有它 —— 这个作业没人跑"
                        % (code, base, row["cron"]))
            continue
        expr, src = found
        if hhmm_of(expr) != hhmm_of(row["cron"]):
            report.fail("A", "%s 时刻对不上：注册表 %s vs %s %s" % (code, row["cron"], src, expr))
        card_hit = next(((card[b][0], card[b][1]) for b in dict.fromkeys(hits) if b in card), None)
        if not card_hit:
            report.fail("A", "%s 在注册表里有调度，但 task-progress-config.json 没有跑 %s 的任务 —— 定时任务卡片看不见它"
                        % (code, base))
        elif hhmm_of(card_hit[0]) and hhmm_of(card_hit[0]) != hhmm_of(row["cron"]):
            report.fail("A", "%s 时刻对不上：注册表 %s vs 卡片配置 %s（%s）"
                        % (code, row["cron"], card_hit[0], card_hit[1]))
        else:
            report.ok("A", "%s ← %s + 卡片(%s) 三处一致（%s）" % (code, src, card_hit[1], row["cron"]))

    orphans = sorted(set(machine) - {b for r in registry.values() for b in r["scripts"]})
    if orphans:
        # 链式调用与不写监控表的辅助作业落在这里：报出来，但不判失败
        report.warn("A", "机器上有、注册表里没有对应脚本（辅助/链式，确认要不要登记）：%s" % ", ".join(orphans))


# ---------------------------------------------------------------- B 契约
MAPPING_RE = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping\b")


def first_string_after(text, pos):
    """注解名之后紧跟的第一个字符串：兼容 @GetMapping、@GetMapping()、@GetMapping("/x")、
    @GetMapping(value = "/x")、@GetMapping({"/a","/b"}) —— 裸写和不带路径的占九成，漏了就会
    把 /admin/kw/config 这类端点错报成"后端没有"。"""
    i = pos
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] != "(":
        return ""
    end = text.find(")", i)
    seg = text[i + 1:end if end > 0 else len(text)]
    m = re.search(r'"([^"]*)"', seg)
    return m.group(1) if m else ""


def backend_routes():
    """controller 的 (method, path)。类级 @RequestMapping 是前缀，方法级才是端点；
    注释掉的实现先剥掉，否则会凭空多出"后端有、前端没调"的端点。"""
    out = set()
    for f in (REPO / "spzx-manager/src/main/java").rglob("*Controller*.java"):
        body = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
        head = body.find("@RequestMapping")
        prefix = first_string_after(body, head + len("@RequestMapping")) if head >= 0 else ""
        for m in MAPPING_RE.finditer(body):
            out.add((m.group(1).upper(), norm_path(prefix + first_string_after(body, m.end()))))
    return out


def read_until_delim(text, i):
    """从 i 起读到同层的 , 或 } 之前（跳过字符串内部），返回 url 的表达式原文"""
    quote, start = None, i
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = None
        elif c in "`'\"":
            quote = c
        elif c in ",}":
            break
        i += 1
    return text[start:i]


def join_url(expr, prefixes):
    """把 url 表达式拼成路径：字符串字面量按序相接，const 前缀（api_name / base_url / base
    三种命名都有）展开，变量与函数调用各算一个路径段。"""
    out = ""
    for part in expr.split("+"):
        part = part.strip()
        m = re.fullmatch(r"`([^`]*)`|'([^']*)'|\"([^\"]*)\"", part)
        if m:
            out += next(g for g in m.groups() if g is not None)
        elif part in prefixes:
            out += prefixes[part]
        elif part:
            out += "${x}"
    return out


def frontend_urls(frontend):
    """src/api/*.js 的 (method, path)。method 缺省按 get；前缀是运行时算出来的那些静态判不了，
    单独返回、不参与判定。"""
    out, unresolved = set(), set()
    for f in sorted((pathlib.Path(frontend) / "src" / "api").glob("*.js")):
        body = strip_comments(f.read_text(encoding="utf-8", errors="ignore"))
        prefixes = dict(re.findall(r"const\s+(\w+)\s*=\s*['\"]([^'\"]*)['\"]", body))
        for m in re.finditer(r"url\s*:\s*", body):
            raw = join_url(read_until_delim(body, m.end()), prefixes)
            # method 可能是三元表达式（`method: isEdit ? 'put' : 'post'`），逐个动词都算一条
            tail = re.search(r"method\s*:\s*([^,}\n]+)", body[m.end():m.end() + 220])
            verbs = re.findall(r"['\"](\w+)['\"]", tail.group(1)) if tail else []
            for name, value in prefixes.items():
                raw = raw.replace("${%s}" % name, value).replace("{%s}" % name, value)
            path = norm_path(raw)
            if path.split("/")[1:2] == ["{}"]:
                unresolved.add(path)
                continue
            for verb in verbs or ["get"]:
                out.add((verb.upper(), path))
    return out, unresolved


def unmatched_calls(fe, be):
    """前端调了、后端没有任何同动词且段级能匹配上的端点"""
    return sorted({(v, p) for (v, p) in fe
                   if not any(v2 == v and path_matches(p, p2) for (v2, p2) in be)})


def check_contract(frontend, report):
    be = backend_routes()
    fe, unresolved = frontend_urls(frontend)
    report.count("backend_routes", len(be))
    report.count("frontend_urls", len(fe))
    for verb, path in unmatched_calls(fe, be):
        report.fail("B", "前端在调、后端没有能匹配上的端点：%s %s" % (verb, path))
    if not unmatched_calls(fe, be):
        report.ok("B", "%d 个前端调用点全部对得上后端路由" % len(fe))
    if unresolved:
        report.warn("B", "%d 条 url 的前缀是运行时拼出来的，静态判不了，不参与判定：%s"
                    % (len(unresolved), ", ".join(sorted(unresolved)[:5])))
    unused = sorted({p for (v, p) in be if not any(v2 == v and path_matches(p2, p) for (v2, p2) in fe)})
    if unused:
        report.warn("B", "后端有、src/api 里没声明的端点 %d 个（别的页面直接调？还是已经没人用）" % len(unused))


# ---------------------------------------------------------------- C 判据副本
def check_copied_predicate(report):
    test = REPO / "spzx-manager/src/test/java/com/joker/spzx/manager/service/ItemOpsParamTest.java"
    if not test.exists():
        report.fail("C", "ItemOpsParamTest 不见了 —— 两份异常流量判据没人逐字比对了")
        return
    if "首页与运营台的异常流量判据逐字一致" not in test.read_text(encoding="utf-8"):
        report.fail("C", "ItemOpsParamTest 里那条「判据逐字一致」的测试被删了/改名了")
    else:
        report.ok("C", "判据副本由 ItemOpsParamTest 守着（本门不重抄规则）")


# ---------------------------------------------------------------- D 告警销案
ALERT_CALL_RE = re.compile(r"--key\s+\"?([\w$-]+)\"?")
DATASET_ARG_RE = re.compile(r"--dataset\s+\"?([\w$-]+)\"?")


def check_alert_resolution(report, registry):
    """cron_alert.py 写的提醒必须带 --dataset，否则后端没有销案依据、提醒永远挂着。
    2026-10-07 查出来的洞：10-02/10-03 那批 cron_skipped 全空着 dataset_code，
    作业早就跑成了，顶栏还挂着「待处理提醒 7」。"""
    writer = REPO / "automation" / "sourcing" / "cron_alert.py"
    if not writer.exists():
        report.fail("D", "cron_alert.py 不在了 —— 这条判据无从核对")
        return
    body = writer.read_text(encoding="utf-8", errors="ignore")
    ins = re.search(r"INSERT INTO sync_alert \(([^)]*)\)", body)
    if not ins or "dataset_code" not in ins.group(1):
        report.fail("D", "cron_alert.py 的 INSERT 不再写 dataset_code —— 提醒会永久挂着")
        return
    callers, missing, unknown = 0, [], []
    # 扫所有 .sh 而不是 cron_*.sh：inventory_cron.sh 不以 cron_ 开头，按名字筛会整文件漏掉，
    # 而"没扫到"不会报红——只认内容里有没有调 cron_alert。
    for sh in sorted((REPO / "automation").rglob("*.sh")):
        if "_archive" in str(sh):
            continue
        text = sh.read_text(encoding="utf-8", errors="ignore")
        if "$ALERT" not in text:
            continue
        # 调用会折行（`--type cron_failed \` 换行接 --msg），先把续行拼成一条再找
        flat = re.sub(r"\\\s*\n\s*", " ", text)
        for cmd in [ln for ln in flat.splitlines() if "$ALERT" in ln and "cron_alert.py" not in ln]:
            callers += 1
            hit = ALERT_CALL_RE.search(cmd)
            key = hit.group(1) if hit else "?"
            got = DATASET_ARG_RE.search(cmd)
            if not got:
                missing.append("%s: %s" % (sh.name, key))
                continue
            code = got.group(1)
            if code.startswith("$"):                # $DS / $DS_ALERT：回到本文件查赋值
                var = code[1:]
                assign = re.search(r"^%s=(\S+)" % re.escape(var), text, re.M)
                code = assign.group(1) if assign else ""
            if code not in registry:
                unknown.append("%s: %s→%s（注册表里没有这个 code）"
                               % (sh.name, key, code or "%s 没赋值" % got.group(1)))
    if missing:
        report.fail("D", "%d 处 cron_alert 调用没带 --dataset，这类提醒写进去就关不掉：%s"
                    % (len(missing), "; ".join(missing)))
    if unknown:
        report.fail("D", "%d 处 --dataset 指向注册表里没有的数据集：%s" % (len(unknown), "; ".join(unknown)))
    if not callers:
        report.fail("D", "一处 cron_alert 调用都没找到 —— 扫描面坏了，别把这次的绿当结论")
        return
    report.count("alert_callers", callers)
    if not missing and not unknown:
        report.ok("D", "%d 处 cron_alert 调用都带 --dataset 且指向注册表里的数据集（销案有依据）" % callers)


# ---------------------------------------------------------------- E 凭据外泄
# 要防的那串口令本身也不写进本仓库（否则这条检查自己就是泄漏点）：从库参数文件现读，
# 口令换了检查自动跟着换。
CNF_CANDIDATES = (os.environ.get("SPZX_MYSQL_CNF"), "/tmp/spzx_my.cnf",
                 os.path.expanduser("~/.spzx/db.cnf"))
SECRET_SCOPE = ("automation", "spzx-manager/src/main/java", "spzx-manager/src/main/resources",
                "spzx-model/src", "spzx-common", "scripts")


def current_secret():
    for p in CNF_CANDIDATES:
        if p and os.path.isfile(p):
            hit = re.search(r"^password=(.+)$",
                            open(p, encoding="utf-8", errors="ignore").read(), re.M)
            if hit:
                return hit.group(1).strip()
    return ""


def check_no_secrets(report):
    """代码与配置里不得出现库口令 —— Python 走 automation/sourcing/dbconf.py 读仓库外的
    600 文件，Java 走 gitignore 的 application-local.yml。
    docs/superpowers 与 .superpowers 是交付台账（历史记录），改写历史等于伪造现场，
    那里的明文靠"换口令"解决，所以不在射程内。"""
    secret = current_secret()
    if not secret:
        report.warn("E", "拿不到口令样本（%s 都不存在），这道检查没跑 —— 别把这次的绿当结论"
                    % " / ".join([c for c in CNF_CANDIDATES if c]))
        return
    # 只判 git 真会带走的东西：application-local.yml 本来就该放着口令，但它被 ignore 了，
    # 按目录扫工作树会把它误报成泄漏。
    listing = sh(["git", "-C", str(REPO), "ls-files"] + [b for b in SECRET_SCOPE])
    if not listing.strip():
        report.warn("E", "git ls-files 在这几个目录下没列到任何文件（不是 git 仓库？），这道检查没跑")
        return
    hits = [rel for rel in listing.splitlines()
            if "_archive" not in rel and rel.rsplit(".", 1)[-1] in ("py", "java", "yml", "sh", "xml")
            and (REPO / rel).is_file()      # 已跟踪但工作区里删掉的，read 会炸
            and secret in (REPO / rel).read_text(encoding="utf-8", errors="ignore")]
    # 扫了多少个文件要报出来：D 那道就是靠文件名筛，整份 inventory_cron.sh 掉出扫描面还一路绿灯
    report.count("secret_scanned", sum(1 for rel in listing.splitlines()
                                       if rel.rsplit(".", 1)[-1] in ("py", "java", "yml", "sh", "xml")))
    if hits:
        report.fail("E", "%d 个已跟踪文件把库口令写进了仓库：%s —— 改读 dbconf.py / application-local.yml"
                    % (len(hits), ", ".join(hits[:6])))
    else:
        report.ok("E", "已跟踪的代码与配置里没有库口令（Python 走 dbconf.py，Java 走 application-local.yml）")


# ---------------------------------------------------------------- 框架
class Report:
    def __init__(self):
        self.failures, self.warnings, self.oks, self.counts = [], [], [], {}

    def fail(self, check, msg):
        self.failures.append((check, msg))

    def warn(self, check, msg):
        self.warnings.append((check, msg))

    def ok(self, check, msg):
        self.oks.append((check, msg))

    def count(self, what, n):
        self.counts[what] = n


def run(frontend=None):
    rep = Report()
    ct, ld = read_crontab(), read_launchd()
    reg, pj = read_registry(), read_progress_json()
    rep.count("crontab", len(ct))
    rep.count("launchd", len(ld))
    rep.count("registry", sum(1 for r in reg.values() if r["monitor"]))
    rep.count("progress_scheduled", sum(1 for t in pj.values() if t["schedule"]))
    check_schedules(ct, ld, reg, pj, rep)
    if frontend:
        check_contract(frontend, rep)
    check_copied_predicate(rep)
    check_alert_resolution(rep, reg)
    check_no_secrets(rep)
    return rep


def selftest(tmp):
    """每道判据各埋一个已知缺陷，确认报得出来 —— 报不出来是门坏了，不是代码干净"""
    global REPO
    box = pathlib.Path(tmp)
    (box / "automation" / "sourcing").mkdir(parents=True)
    (box / "automation" / "sourcing" / "task-progress-config.json").write_text(
        json.dumps({"tasks": [{"key": "job_a", "schedule": "每日 05:00", "script": "a.py"}]
                             + [{"key": "x%d" % i, "schedule": "每日 01:00", "script": "x%d.py" % i}
                                for i in range(FLOOR["progress_scheduled"])]}), encoding="utf-8")

    reg = {"job_a": {"cron": "0 6 * * *", "scripts": {"a.py"}, "monitor": True},   # 时刻不一致 + 卡片不一致
           "job_b": {"cron": "", "scripts": {"b.py"}, "monitor": True},            # 缺 cron_expr
           "job_c": {"cron": "30 4 * * *", "scripts": {"c.py"}, "monitor": True},  # 机器上没人跑
           "job_d": {"cron": "0 5 * * *", "scripts": {"d.py"}, "monitor": True},   # 卡片里没登记
           "job_e": {"cron": "0 5 * * *", "scripts": {"e.py"}, "monitor": False}}  # 不监控，不该报
    rep = Report()
    check_schedules([("0 5 * * *", "python a.py d.py e.py")], [], reg,
                    {"job_a": {"schedule": "每日 05:00", "scripts": {"a.py"}}}, rep)
    a = "\n".join(m for c, m in rep.failures if c == "A")
    for want in ("时刻对不上", "没写 cron_expr", "没人跑", "task-progress-config.json 没有"):
        assert want in a, "夹具缺陷「%s」没报出来 → %s" % (want, a)
    assert "job_e" not in a, "夹具：不监控的项被误报 → %s" % a

    # B：三种真实写法各来一条 —— 裸 @GetMapping、`${base}/x`、`'a/b/' + id` 拼接
    api = box / "src" / "api"
    api.mkdir(parents=True)
    (api / "demo.js").write_text(
        "import request from '@/utils/request'\nconst api_name = '/admin/demo'\n"
        "const base_url = 'admin/demo'\n"
        "export const A = () => request({ url: `${api_name}/exists/${id}`, method: 'get' })\n"
        "export const B = () => request({ url: 'admin/demo/ghost', method: 'post' })\n"
        "export const C = () => request({ url: base_url + '/tail/' + roleId, method: 'get' })\n"
        "export const D = () => request({ url: `${api_name}`, method: 'put' })\n"
        "export const F = (d, isEdit) => request({ url: api_name + '/tail', method: isEdit ? 'put' : 'post', data: d })\n"
        "export const E = () => request({ url: `${runtime()}/all`, method: 'get' })\n", encoding="utf-8")
    ctl = box / "spzx-manager/src/main/java/com/joker/spzx/manager/controller"
    ctl.mkdir(parents=True)
    (ctl / "DemoController.java").write_text(
        '@RequestMapping("/admin/demo")\npublic class DemoController {\n'
        "    @GetMapping\n    public Object get() { return null; }\n"
        "    @PutMapping\n    public Object put() { return null; }\n"
        '    @GetMapping("/exists/{id}")\n    public Object e() { return null; }\n'
        '    @GetMapping(value = "/tail/{roleId}")\n    public Object t() { return null; }\n'
        '    @PutMapping("/tail")\n    public Object tp() { return null; }\n'
        '    @PostMapping("/tail")\n    public Object tc() { return null; }\n'
        "    // @DeleteMapping(\"/ghost\") 已注释掉，不该被当成端点\n}", encoding="utf-8")
    old, REPO = REPO, box
    try:
        fe, unresolved = frontend_urls(box)
        be = backend_routes()
    finally:
        REPO = old
    assert ("PUT", "/admin/demo") in fe and ("GET", "/admin/demo/tail/{}") in fe, "前端解析不对：%s" % fe
    # method 是三元表达式的（`isEdit ? 'put' : 'post'`）要两个动词都算一条，漏一个就会假报死调用
    assert {("PUT", "/admin/demo/tail"), ("POST", "/admin/demo/tail")} <= fe, \
        "三元 method 没展开：%s" % sorted(fe)
    assert "/{}/all" in unresolved and not any(p.startswith("/{}/") for _, p in fe), "运行时前缀该排除还判进来了"
    assert ("GET", "/admin/demo") in be, "裸 @GetMapping 没认出来（后端类级前缀单独成端点）"
    assert ("GET", "/admin/demo/exists/{}") in be and ("GET", "/admin/demo/tail/{}") in be, "后端解析不对：%s" % be
    assert not any("/ghost" in p for _, p in be), "注释掉的端点被当成真的了"
    ghost = unmatched_calls(fe, be)
    assert ("POST", "/admin/demo/ghost") in ghost, "该报的死调用没报 → %s" % ghost
    for good in [("GET", "/admin/demo/exists/{}"), ("PUT", "/admin/demo"),
                 ("GET", "/admin/demo/tail/{}"), ("PUT", "/admin/demo/tail"),
                 ("POST", "/admin/demo/tail")]:
        assert good not in ghost, "不该报的被误报 → %s" % ghost
    assert path_matches("/admin/demo/exists/{}", "/admin/demo/exists/7"), "路径变量没做双向匹配"
    assert not path_matches("/admin/demo/ghost", "/admin/demo/exists/{}"), "不该匹配的匹配上了"

    rep = Report()
    svc = box / "spzx-manager/src/test/java/com/joker/spzx/manager/service"
    svc.mkdir(parents=True)
    (svc / "ItemOpsParamTest.java").write_text("class X { void 别的测试() {} }", encoding="utf-8")
    old, REPO = REPO, box
    try:
        check_copied_predicate(rep)
    finally:
        REPO = old
    assert rep.failures, "夹具：测试被改名却没报 → C 这道判据是假的"

    # D：三种坏形各造一条 —— 没带 --dataset / 指向没注册的数据集 / 写入方不再写 dataset_code
    dbox = pathlib.Path(tmp) / "d"
    (dbox / "automation" / "sourcing").mkdir(parents=True)
    (dbox / "automation" / "tb-auto").mkdir(parents=True)
    (dbox / "automation" / "sourcing" / "cron_alert.py").write_text(
        'cur.execute("INSERT INTO sync_alert (alert_type, dataset_code, shop_id, old_value, '
        'message, status, create_time) VALUES (%s,%s,%s,%s,%s,0,%s)")', encoding="utf-8")
    (dbox / "automation" / "sourcing" / "cron_bad_nodash.sh").write_text(
        'ALERT=$DIR/cron_alert.py\n$PY "$ALERT" --key job_x --msg "没带 dataset" > /dev/null 2>&1\n',
        encoding="utf-8")
    (dbox / "automation" / "sourcing" / "cron_bad_unknown.sh").write_text(
        'DS=not_registered\n$PY "$ALERT" --key job_y --dataset "$DS" --msg "x"\n', encoding="utf-8")
    (dbox / "automation" / "tb-auto" / "cron_bad_writer.sh").write_text(
        '$PY "$ALERT" --key job_z --platform 1 --type cron_failed \\\n'
        '  --dataset item_daily_sycm --msg "折行也要认出来"\n', encoding="utf-8")
    rep = Report()
    old, REPO = REPO, dbox
    try:
        check_alert_resolution(rep, {"item_daily_sycm": {}})
    finally:
        REPO = old
    d = "\n".join(m for c, m in rep.failures)
    assert "没带 --dataset" in d and "job_x" in d, "夹具：漏 --dataset 没报 → %s" % d
    assert "注册表里没有" in d and "not_registered" in d, "夹具：dataset 写错没报 → %s" % d
    assert "job_z" not in d, "夹具：折行的正常调用被误报 → %s" % d
    # 写入方不再写 dataset_code 时要报红
    (dbox / "automation" / "sourcing" / "cron_alert.py").write_text(
        'cur.execute("INSERT INTO sync_alert (alert_type, shop_id, old_value, message, status, '
        'create_time) VALUES (%s,%s,%s,%s,%s,0,%s)")', encoding="utf-8")
    rep = Report()
    old, REPO = REPO, dbox
    try:
        check_alert_resolution(rep, {"item_daily_sycm": {}})
    finally:
        REPO = old
    assert "INSERT 不再写 dataset_code" in "\n".join(m for c, m in rep.failures), \
        "夹具：写入方掉了 dataset_code 没报 → D 这道判据是假的"

    # E：口令回到仓库时要报红（放一个假的 .py 进扫描范围）。
    # 口令样本从库参数文件现读，判据才不是"只认某一串写死的字符串"。
    secret = current_secret()
    if not secret:
        print("selftest: A/B/C/D 已验；E 跳过（库参数文件都不存在，取不到口令样本，别以为 E 验过）")
    elif subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        print("selftest: E 跳过（没有 git，判不了「已跟踪」这个口径）")
    else:
        # E 判的是「git 会带走的文件」，所以夹具要先落文件、再 git add，删完还要同步索引
        subprocess.run(["git", "init", "-q"], cwd=str(box), capture_output=True)
        leaky = box / "automation" / "sourcing" / "leaky.py"
        leaky.write_text('DB = {"password": "%s"}' % secret, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(box), capture_output=True)
        rep = Report()
        old, REPO = REPO, box
        try:
            check_no_secrets(rep)
        finally:
            REPO = old
        assert rep.failures and "leaky.py" in rep.failures[0][1], \
            "夹具：口令回潮没报 → E 这道判据是假的"
        leaky.unlink()
        subprocess.run(["git", "add", "-A"], cwd=str(box), capture_output=True)
        rep = Report()
        old, REPO = REPO, box
        try:
            check_no_secrets(rep)
        finally:
            REPO = old
        assert not rep.failures, "夹具：删掉口令后仍报红 → %s" % rep.failures
    print("selftest: A 埋 5 种情形 / B 解析与匹配 / C 改名检测 / D 三种销案缺陷 / E 口令回潮，全部按预期报出")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="先证明这些判据能报红")
    args = ap.parse_args()

    if args.selftest:
        with tempfile.TemporaryDirectory() as tmp:
            selftest(tmp)
        return 0

    frontend = next((c for c in FRONTEND_CANDIDATES if c and os.path.isdir(os.path.join(c, "src", "api"))), None)
    if not frontend:
        print("!! 找不到前端 src/api（可用 SPZX_FRONTEND_SRC 覆盖）—— 检查 B 不会跑")
        return 2
    try:
        rep = run(frontend)
    except Exception as e:
        print("!! 门跑不完：%s" % e)
        return 2

    for what, n in sorted(rep.counts.items()):
        floor = FLOOR.get(what)
        bad = floor is not None and n < floor
        print("!! %-18s %5d  ← 低于下限 %d，扫描面缩了，结论不可信" % (what, n, floor) if bad
              else "   %-18s %5d" % (what, n))
    shrunk = [w for w, n in rep.counts.items() if FLOOR.get(w) is not None and n < FLOOR[w]]
    for check, msg in rep.oks:
        print("ok   [%s] %s" % (check, msg))
    for check, msg in rep.warnings:
        print("warn [%s] %s" % (check, msg))
    for check, msg in rep.failures:
        print("FAIL [%s] %s" % (check, msg))
    print("\n%d 项通过 / %d 项警告 / %d 项失败" % (len(rep.oks), len(rep.warnings), len(rep.failures)))
    return 1 if (rep.failures or shrunk) else 0


if __name__ == "__main__":
    sys.exit(main())
