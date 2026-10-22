# 调度体系优化（两窗口 + 事件驱动 + 可靠性四件套 + 磁盘卫生）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 spec `docs/superpowers/specs/2026-10-19-schedule-optimization-design.md` 落地方案 A：凌晨写窗口链式化、中午只读窗口、19:30 事件驱动补偿、防僵死守卫/跳过升级/当页重试/登录态预检四件套、磁盘卫生每日清理。

**Architecture:** 共享守卫库进 `chrome_guard.sh`（全包装已 source 它）；夜窗链由新 `run_night_window.sh` 串起现有 `run_stock_refresh.sh`→`run_stock_sync.sh`→`chrome_kill.sh`；事件判定独立成可单测的 `stock_event_check.py`；plist 全部整体重写 XML；清理脚本挂 db_daily 第 5 步。

**Tech Stack:** bash + Python 3.9（automation/venv）+ Playwright async + launchd plist + crontab + unittest。

## Global Constraints

- **绝不 git commit / git add**（仓库纪律，owner 明令）——所有改动留工作区；计划里没有 commit 步骤，每任务以「验证通过」收尾。
- Python 统一 `automation/venv/bin/python`；单测用 unittest（**无 pytest**），跑法 `venv/bin/python -m unittest <模块> -v`（在 automation/sourcing 下）。
- MySQL 一律 `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx`（口令不进命令行；/tmp cnf 若丢失先 `python3 scripts/mysql-cnf.py` 重建）。
- plist 纪律：**整体重写 XML**（PlistBuddy 嵌套 -c 会写坏整份文件）；读用 `plutil -extract <kp> xml1 -o - <f>`；改后 `plutil -lint` + `launchctl bootout gui/$(id -u)/<label>` + `launchctl bootstrap gui/$(id -u) <file>` + `launchctl print` 核对；**同步 `scripts/launchd/` 仓库副本并 `cmp`**。
- 9222 Chrome 红线：不 `pkill` 全局 Chrome（只许 `pkill -f "remote-debugging-port=9222"`，且仅 chrome_kill.sh 这么做）；脚本不新增 `b.close()`（沿用 `detect_stock_night.py` 的只关自己 page 模式）。
- 本机无 GNU timeout：硬停用 `perl -e 'alarm N; exec @ARGV'`；crontab 安装历史上会挂死（10-07），10-19 编辑成功过——**所有 crontab 写操作都套 alarm 20s 兜底**，卡死即弃并报告用户。
- 用户长任务（`assign_shop_category_v2` / `edit_brand_title_batch` / `isv_sku_match`）**永不自动杀**，守卫只纯 skip。
- crontab 改动前先备份：`crontab -l > /tmp/crontab.bak.20261019`。
- 每任务只动自己 Files 清单里的文件。

---

### Task 1: backfill 建档收尾改造 + 重启（⏰ 时间敏感：今晚 21:30 前必须完成）

**Files:**
- Modify: `.superpowers/sdd/2026-10-18-source-stock-monitor/run_backfill_nights.sh`

**Interfaces:**
- Produces: 后台常驻 launcher（nohup），今晚 21:30 自起 `backfill_offer_archive.py`，02:45 硬停，待建档=0 自退。后续任务不依赖它，但今晚 03:00 夜窗依赖它 02:45 前退出。

- [ ] **Step 1: 确认 launcher 已死 + 查死因**

```bash
pgrep -fl "backfill" ; echo "exit=$?"
tail -5 /Users/qyk9527/ideaProject/spzx-parent/.superpowers/sdd/2026-10-18-source-stock-monitor/backfill_nights.log
```
Expected: `exit=1`（无进程）；日志末行 `夜1 结束 rc=0 待建档 600`（之后无输出=进程未进入下一夜循环就没了）。把死因结论（能查到什么写什么）记进任务报告；无论如何按 Step 3 用 nohup+disown 双保险重启。

- [ ] **Step 2: 改窗口 21:30 / 硬停 02:45 / 删等 alimama 循环**

对 `run_backfill_nights.sh` 做三处修改——头部注释 L2-4 改为：

```bash
# P1 全量建档 夜间分段 launcher（SDD Task 4，spec 2026-10-18；窗口 2026-10-19 改 21:30-02:45
# 避开 03:00 夜窗链——spec 2026-10-19-schedule-optimization §3。alimama 已挪 12:06，等采集循环删除）
```

L17 等待时刻（`2230` → `2130`）：

```bash
  while [ "$(date +%H%M)" -lt 2130 ]; do sleep 300; done
```

L18-20 三行（等 alimama 采集结束的 for/if）**整段删除**——alimama 已不在夜间跑。L31 alarm（20000 → 18900，21:30+5.25h=02:45）：

```bash
  perl -e 'alarm shift; exec @ARGV' 18900 $PY backfill_offer_archive.py --delay 6 >> /tmp/backfill_night_run.log 2>&1
```

- [ ] **Step 3: 语法验证 + nohup 重启**

```bash
bash -n /Users/qyk9527/ideaProject/spzx-parent/.superpowers/sdd/2026-10-18-source-stock-monitor/run_backfill_nights.sh && echo SYNTAX_OK
nohup bash /Users/qyk9527/ideaProject/spzx-parent/.superpowers/sdd/2026-10-18-source-stock-monitor/run_backfill_nights.sh > /dev/null 2>&1 &
disown
sleep 3
pgrep -fl run_backfill_nights
tail -1 /Users/qyk9527/ideaProject/spzx-parent/.superpowers/sdd/2026-10-18-source-stock-monitor/backfill_nights.log
```
Expected: SYNTAX_OK；pgrep 有 pid；日志新行 `launcher 启动, 当前待建档 62x`。

- [ ] **Step 4: 留待观察**（不阻塞后续任务）：今晚 ~23:30 后 `backfill_nights.log` 应出现「夜1 结束 … 待建档 0 / 建档完成, launcher 退出」。

---

### Task 2: chrome_guard.sh 共享守卫库扩展 + check_login.py（含单测）

**Files:**
- Modify: `automation/sourcing/chrome_guard.sh`
- Create: `automation/sourcing/check_login.py`
- Test: `automation/sourcing/test_login_wall.py`、`automation/sourcing/test_chrome_guard.sh`（可执行 bash 夹具）

**Interfaces:**
- Produces（后续所有包装任务依赖，签名逐字一致）:
  - `guard_task <pattern> <max_minutes>` — bash 函数；返回 0=可继续（无进程，或 hung 进程已被终止），返回 1=有进程且未超龄（调用方应 skip）。hung 判定=任一匹配进程 etime ≥ max_minutes 分钟；只杀匹配的 python/脚本进程，不写告警不写台账（被杀任务的 wrapper 自己走 rc≠0 路径补台账）。
  - `bump_skip <key>` — 计数 +1 并输出新值；`clear_skip <key>` — 清零；`skip_note <key>` — 连续 ≥2 时输出前缀 `【已连续 N 天未跑】数据断档，需人工介入 `（注意尾部空格），否则输出空串。计数文件 `/tmp/spzx_skipcnt_<key>`。
  - `ensure_login` — bash 函数；调 check_login.py，exit 0=登录态 OK / 非 0=登录墙或探测异常。
  - check_login.py 决策纯函数 `is_login_wall(url, has_password_input) -> bool`。

- [ ] **Step 1: 先写失败测试 test_login_wall.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""is_login_wall 纯函数单测（spec 2026-10-19 §4.4）"""
import unittest
from check_login import is_login_wall


class TestLoginWall(unittest.TestCase):
    def test_console_url_ok(self):
        self.assertFalse(is_login_wall(
            "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818", False))

    def test_taobao_login_redirect(self):
        self.assertTrue(is_login_wall(
            "https://login.taobao.com/member/login.jhtml?redirect=ufuwu", False))

    def test_1688_login_redirect(self):
        self.assertTrue(is_login_wall("https://login.1688.com/member/signin.htm", False))

    def test_password_input_on_page(self):
        self.assertTrue(is_login_wall("https://ufuwu.1688.com/page/fuwu_work_isv_container.htm", True))

    def test_empty_url_no_input(self):
        self.assertFalse(is_login_wall("", False))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_login_wall -v
```
Expected: FAIL（`ModuleNotFoundError: check_login`）。

- [ ] **Step 3: 写 check_login.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_login.py — 9222 登录态预检（spec 2026-10-19-schedule-optimization §4.4）

连 CDP 9222 打开 ISV 控制台，判是否被踢到登录墙。exit 0=登录态 OK / 1=登录墙 / 2=探测异常。
只开自己的标签、只关自己的标签（绝不 b.close()，沿用 detect_stock_night.py 模式）。
不自动重登录——登录墙=人工扫码，包装层 skip 并写显式告警。
"""
import asyncio
import sys

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')

CONSOLE_URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"


def is_login_wall(url, has_password_input):
    """登录墙判定（纯函数）：控制台 URL 被重定向到登录域，或页面上有可见密码输入框。"""
    if any(h in (url or "") for h in ("login.taobao.com", "login.1688.com", "member/login")):
        return True
    return bool(has_password_input)


async def run():
    from cdp_utils import connect_cdp, new_page_quiet
    b, ctx = await connect_cdp(
        9222,
        keep_urls=["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com",
                   "taobao.com", "1688.com"],
        log=lambda m: print(m, flush=True))
    page = await new_page_quiet(ctx)
    try:
        await page.goto(CONSOLE_URL, timeout=30000)
        await asyncio.sleep(6)
        url = page.url
        pw = await page.evaluate("""() => {
          const vis = (i) => { const r = i.getBoundingClientRect();
                               return r.width > 20 && r.height > 10; };
          for (const i of document.querySelectorAll('input[type=password]'))
            if (vis(i)) return true;
          for (const f of document.querySelectorAll('iframe')) {
            try { const d = f.contentDocument; if (!d) continue;
              for (const i of d.querySelectorAll('input[type=password]'))
                if (vis(i)) return true; } catch (e) {}
          }
          return false; }""")
        wall = is_login_wall(url, pw)
        print(f"CHECK {'LOGIN_WALL' if wall else 'OK'} url={url[:120]} pw={pw}")
        return 1 if wall else 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass


def main():
    try:
        sys.exit(asyncio.run(run()))
    except Exception as e:
        print(f"CHECK PROBE_ERROR {e!r}")
        sys.exit(2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑单测确认通过**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_login_wall -v
```
Expected: 5 tests PASS。

- [ ] **Step 5: 活体验证（当前 9222 应有登录态）**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
source chrome_guard.sh && ensure_chrome && echo CHROME_OK
../venv/bin/python check_login.py; echo "exit=$?"
```
Expected: `CHECK OK url=https://ufuwu.1688.com/...`，exit=0。若得 LOGIN_WALL：说明登录态真掉了，报告用户（今天人工扫码一次），**不改代码**——这正是它该报的。

- [ ] **Step 6: chrome_guard.sh 追加共享函数（文件末尾追加，不动 ensure_chrome）**

```bash
# ---------- 共享守卫/台账辅助（spec 2026-10-19-schedule-optimization §4.1/4.2/4.4） ----------

guard_task() {
  # 用法: guard_task <pattern> <max_minutes>；返回 0=可继续（hung 已被终止）, 1=占用中应 skip。
  # 只对定时任务模式使用；用户长任务（归类v2/品牌/规格匹配）用纯 pgrep && skip, 永不自动杀。
  local pat="$1" maxm="${2:-60}" pids p et s estale=0
  pids=$(pgrep -f "$pat" 2>/dev/null) || return 0
  for p in $pids; do
    et=$(ps -o etime= -p "$p" 2>/dev/null | tr -d ' ')
    [ -z "$et" ] && continue
    s=$(echo "$et" | awk -F'[-:]' '{if(NF==4)print $1*86400+$2*3600+$3*60+$4;
                                    else if(NF==3)print $1*3600+$2*60+$3;
                                    else print $1*60+$2}')
    [ "${s:-0}" -ge $((maxm * 60)) ] && estale=1
  done
  [ "$estale" = "1" ] || return 1
  echo "[$(date '+%F %T')] [guard_task] $pat 超过 ${maxm}min 判定 hung, 终止: $pids" >> /tmp/chrome_guard.log
  pkill -TERM -f "$pat" 2>/dev/null
  sleep 10
  pgrep -f "$pat" >/dev/null 2>&1 && pkill -KILL -f "$pat" 2>/dev/null
  return 0
}

_skipcnt_file() { echo "/tmp/spzx_skipcnt_$1"; }

bump_skip() {
  local f n
  f=$(_skipcnt_file "$1")
  n=$(( $(cat "$f" 2>/dev/null || echo 0) + 1 ))
  echo "$n" > "$f"
  echo "$n"
}

clear_skip() { echo 0 > "$(_skipcnt_file "$1")"; }

skip_note() {
  local n
  n=$(cat "$(_skipcnt_file "$1")" 2>/dev/null || echo 0)
  if [ "${n:-0}" -ge 2 ]; then
    echo "【已连续 ${n} 天未跑】数据断档，需人工介入 "
  fi
}

ensure_login() {
  /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python \
    /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/check_login.py >/dev/null 2>&1
}
```

- [ ] **Step 7: 写 bash 夹具测试 test_chrome_guard.sh 并跑**

```bash
#!/bin/bash
# guard_task/bump_skip/skip_note 夹具测试（不碰真 9222；模式用 zz_test_ 前缀防误杀）
set -u
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
source "$DIR/chrome_guard.sh"
PAT=zz_test_hung_probe_
FAIL=0

# 用例1: max=0 → 任何在跑进程都算 hung → 被终止, guard_task 返回 0
sleep 300 & P1=$!
pkill -TERM -f "$PAT" 2>/dev/null; sleep 0.2
bash -c "exec -a ${PAT}a sleep 300" &   # argv 含模式串
sleep 0.5
pgrep -f "$PAT" >/dev/null || { echo "夹具异常: 没起进程"; exit 1; }
if guard_task "$PAT" 0; then :; else echo "FAIL 用例1: 返回非0"; FAIL=1; fi
sleep 1
pgrep -f "$PAT" >/dev/null && { echo "FAIL 用例1: 进程没被杀"; FAIL=1; pkill -KILL -f "$PAT"; }

# 用例2: max=1 → 新进程未超龄 → 返回 1（skip）
bash -c "exec -a ${PAT}b sleep 300" &
sleep 0.5
if guard_task "$PAT" 1; then echo "FAIL 用例2: 应返回1(skip)"; FAIL=1; fi
pkill -KILL -f "$PAT" 2>/dev/null

# 用例3: 无进程 → 返回 0
guard_task "$PAT" 0 || { echo "FAIL 用例3: 无进程应放行"; FAIL=1; }

# 用例4: skip 计数
rm -f /tmp/spzx_skipcnt_t1
[ "$(bump_skip t1)" = "1" ] || { echo "FAIL bump 首次应为1"; FAIL=1; }
[ "$(bump_skip t1)" = "2" ] || { echo "FAIL bump 二次应为2"; FAIL=1; }
[ "$(skip_note t1)" = "【已连续 2 天未跑】数据断档，需人工介入 " ] || { echo "FAIL skip_note@2"; FAIL=1; }
clear_skip t1
[ -z "$(skip_note t1)" ] || { echo "FAIL clear 后应为空"; FAIL=1; }

kill $P1 2>/dev/null
[ "$FAIL" = "0" ] && echo ALL_PASS || exit 1
```

```bash
chmod +x /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/test_chrome_guard.sh
/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/test_chrome_guard.sh
```
Expected: `ALL_PASS`（用例1 里 `exec -a` 把 argv 改成模式串以精确模拟「名字可匹配的 hung 进程」；测试后必须无 zz_test 残留进程：`pgrep -fl zz_test_` 为空）。

---

### Task 3: run_stock_sync.sh 参照改造（guard_task 自互斥 + skip 升级 + ensure_login + clear_skip）

**Files:**
- Modify: `automation/sourcing/run_stock_sync.sh`

**Interfaces:**
- Consumes: Task 2 的 `guard_task/bump_skip/clear_skip/skip_note/ensure_login`（chrome_guard.sh 已被本文件 source）。
- Produces: 其余包装照抄本任务的改造模式（结构：`guard_task <自身模式> <max>` 放首位 + 用户长任务纯 skip + `ensure_chrome` 后 `ensure_login` + skip() 里 `bump_skip`/`skip_note` + 成功路径 `clear_skip`）。

- [ ] **Step 1: 改造脚本（守卫段 L22-36 整段替换、skip() 替换、成功路径加 clear_skip）**

skip() 整体替换为：

```bash
skip() {
  local n
  n=$(bump_skip stock_sync)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过本轮"
  $PY "$ALERT" --key stock_sync --dataset "$DS" \
    --msg "$(skip_note stock_sync)库存同步未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}
```

Chrome/守卫段（原 L22-36）替换为：

```bash
# 守卫: Chrome 9222 不在线 → 静默拉起；再验登录态（掉了=显式告警+skip, 不自动重登）
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
# 守卫: 自互斥+防僵死（上一轮 >60min 判 hung 终止后放行）
guard_task isv_stock_sync 60 || skip "上一轮库存同步未结束"
# 守卫: 定时任务互避（超龄自动终止；此处 max 均为各任务正常耗时的 2 倍以上）
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
# 守卫: 用户长任务（合法小时级长跑, 永不自动杀）→ 纯避让
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f backfill_offer_archive > /dev/null && skip "P1建档长跑占用同一 Chrome"
```

成功路径（原 L45 `if [ "$rc" = "0" ]; then` 块内、`$PY "$BATCH" end ... success` 之前）加一行：

```bash
  clear_skip stock_sync
```

- [ ] **Step 2: 语法验证 + dry-run 模式不触发真写**

```bash
bash -n /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_stock_sync.sh && echo SYNTAX_OK
pgrep -f isv_stock_sync; echo "self_running_exit=$?"
```
Expected: SYNTAX_OK；当前无 isv_stock_sync 进程（guard_task 自互斥在 19:30 事件触发时才真正起作用）。

- [ ] **Step 3: 冒烟——登录态链路 + python 层 dry-run（包装守卫段的登录态路径借此活体验证）**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
source chrome_guard.sh && ensure_chrome && ensure_login; echo "login_exit=$?"
../venv/bin/python isv_stock_sync.py --pages 1 --dry-run 2>&1 | tail -5
```
Expected: `login_exit=0`；python 输出含 `已关联货源 …` → `在售口径: 销售中 …` → `[1/N] DRY 已选100/100`。`skip_note` 空计数不升级（/tmp/spzx_skipcnt_stock_sync 当前值即今天 12:30 failed 的 1，属正常历史）。

---

### Task 4: 其余 4 个定时包装同款改造

**Files:**
- Modify: `automation/sourcing/run_stock_refresh.sh`
- Modify: `automation/sourcing/run_onsale_scan.sh`
- Modify: `automation/sourcing/cron_sycm_snapshot.sh`
- Modify: `automation/tb-auto/cron_alimama_promo.sh`

**Interfaces:**
- Consumes: Task 2 共享函数；Task 3 的改造模式。
- 注：`run_stock_refresh.sh`（夜巡，只开 1688 详情页，不需要卖家登录态）**不加 ensure_login**，其余三个（ISV/卖家控制台类）都加。

- [ ] **Step 1: run_stock_refresh.sh**

skip() 换成（key=stock_refresh）：

```bash
skip() {
  local n
  n=$(bump_skip stock_refresh)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过本轮"
  $PY "$ALERT" --key stock_refresh --dataset "$DS" \
    --msg "$(skip_note stock_refresh)分级刷新未跑: $1" > /dev/null 2>&1
  local bid; bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}
```

守卫段（原 L19-25）替换（另在 `source` 行之前、`cd "$DIR"` 之后加一行抖动 `sleep $((RANDOM % 300))`——夜窗是窗口首任务）：

```bash
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
guard_task detect_stock_night 130 || skip "上一轮库存巡检未结束"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f backfill_offer_archive > /dev/null && skip "P1建档长跑占用同一 Chrome"
```

成功路径 `if [ "$rc" = "0" ]; then` 块内加 `clear_skip stock_refresh`。

- [ ] **Step 2: run_onsale_scan.sh**

skip()（key=onsale_scan，注意它有 `--platform 1`）：

```bash
skip() {
  local n
  n=$(bump_skip onsale_scan)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过" >> "$LOG"
  $PY "$ALERT" --key onsale_scan --dataset "$DS" --platform 1 \
    --msg "$(skip_note onsale_scan)在售扫描未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}
```

守卫段（原 L20-23）替换（`cd "$DIR"` 后加抖动 `sleep $((RANDOM % 180))`——窗口内后续任务小抖动）：

```bash
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
guard_task sync_onsale 30 || skip "上一轮未结束"
guard_task sycm_item_snapshot 60 || skip "生意参谋快照占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f assign_shop_category_v2 >/dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch >/dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match >/dev/null && skip "ISV规格匹配占用同一 Chrome"
```

成功路径加 `clear_skip onsale_scan`（`if [ "$rc" = "0" ]` 块内）。文件末尾既有 `ensure_chrome   # 退出兜底` 保留不动。

- [ ] **Step 3: cron_sycm_snapshot.sh**

skip()（key=sycm_snapshot）同款，msg 改「生意参谋每日快照未落库」；在 `cd "$DIR"` 后加抖动 `sleep $((RANDOM % 180))`；守卫段（原 L21-25）替换：

```bash
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
guard_task sycm_item_snapshot 60 || skip "上一轮快照未结束"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
```

成功路径（`if [ "$V" = "partial" ]` 的 else 分支与 partial 分支都算「本轮跑过了」——`clear_skip sycm_snapshot` 放在 `if [ "$rc" = "0" ]; then` 进入处、verdict 判定之前）。

- [ ] **Step 4: cron_alimama_promo.sh（tb-auto 侧，source 的就是同一个 chrome_guard.sh）**

skip()（key=alimama_promo，DATASETS 循环不变）：

```bash
skip() {
  local n
  n=$(bump_skip alimama_promo)
  echo "[$(date '+%F %T')] ($n) $1, 跳过采集" >> "$LOG"
  $PY "$ALERT" --key "$KEY" --dataset "$DS" --platform 1 \
    --msg "$(skip_note alimama_promo)推广日报采集未落库: $1" > /dev/null 2>&1
  for ds in $DATASETS; do
    local bid
    bid=$($PY "$BATCH" begin --dataset "$ds" --platform 1)
    $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  done
  exit 0
}
```

守卫段（原 L34-41）替换（`cd "$DIR"` 后加抖动 `sleep $((RANDOM % 300))`——中午窗口首任务大抖动）：

```bash
# 守卫 1: MySQL 不在线就不必再往下走
nc -z 127.0.0.1 3306 || skip "MySQL 3306 未监听"
# 守卫 2: Chrome 9222 静默拉起 + 登录态预检
source "$SRC/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
# 守卫 3: 定时任务互避（超龄自动终止）+ 用户长任务纯避让
guard_task collect_alimama_promo 120 || skip "上一轮采集未结束"
guard_task sycm_item_snapshot 60 || skip "生意参谋快照占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
```

成功路径：`if [ "$rc" = "0" ]; then` 块内（现文件没有此 if——rc 处理在 L54-58；在 L50 `echo 退出码` 后加）：

```bash
if [ "$rc" = "0" ]; then clear_skip alimama_promo; fi
```

- [ ] **Step 5: 语法 + 夹具回归**

```bash
for f in automation/sourcing/run_stock_refresh.sh automation/sourcing/run_onsale_scan.sh \
         automation/sourcing/cron_sycm_snapshot.sh automation/tb-auto/cron_alimama_promo.sh; do
  bash -n "/Users/qyk9527/ideaProject/spzx-parent/$f" || echo "SYNTAX_FAIL $f"
done; echo SYNTAX_DONE
/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/test_chrome_guard.sh
```
Expected: 无 SYNTAX_FAIL；ALL_PASS。

---

### Task 5: isv_stock_sync.py 当页重试×2（含可单测纯函数）

**Files:**
- Modify: `automation/sourcing/isv_stock_sync.py:271-276`
- Test: `automation/sourcing/test_isv_stock_sync.py`（新建）

**Interfaces:**
- Produces: 纯函数 `page_select_ok(sel, n_rows) -> bool`（sel 为 select_all_page 返回的字符串列表）；页循环内重试 ≤3 次（首次 + 2 重试），重试动作=清弹窗→(尝试>1 时先 uncheck 再 check 强制重发事件)→重选。

- [ ] **Step 1: 先写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_select_ok 纯函数单测（spec 2026-10-19-schedule-optimization §4.3）"""
import unittest
from isv_stock_sync import page_select_ok


class TestPageSelectOk(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(page_select_ok(["已选100/100"], 100))

    def test_with_suffix(self):
        self.assertTrue(page_select_ok(["已选100/共100"], 100))

    def test_zero_selected_is_bad(self):
        self.assertFalse(page_select_ok(["已选0/100"], 100))

    def test_partial_is_bad(self):
        self.assertFalse(page_select_ok(["已选37/100"], 100))

    def test_empty_sel(self):
        self.assertFalse(page_select_ok([], 100))

    def test_none_sel(self):
        self.assertFalse(page_select_ok(None, 100))

    def test_unrelated_text(self):
        self.assertFalse(page_select_ok(["已关联货源(4183)"], 100))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_isv_stock_sync -v
```
Expected: FAIL（`cannot import name 'page_select_ok'`）。

- [ ] **Step 3: 实现纯函数 + 改页循环（L271-276）**

在 `select_all_page`（L108）之后加：

```python
def page_select_ok(sel, n_rows):
    """全选校验（纯函数）：已选计数必须=本页行数（容忍『已选N/共N』式文案）。"""
    want = f"已选{n_rows}/{n_rows}"
    return any(want in s or f"已选{n_rows}/" in s for s in (sel or []))
```

页循环内原 L271-276：

```python
            n_rows = await fr.locator(".ant-table-row").count()
            sel = await select_all_page(fr)
            want = f"已选{n_rows}/{n_rows}"
            if not any(want in s or f"已选{n_rows}/" in s for s in sel):
                log(f"第 {pg} 页选中异常: {sel}")
                return 6
```

替换为（重试 ≤3 次；rc=6 只在 3 次全败后返回）：

```python
            ok = False
            for attempt in range(3):
                n_rows = await fr.locator(".ant-table-row").count()
                sel = await select_all_page(fr)
                if page_select_ok(sel, n_rows):
                    ok = True
                    break
                log(f"第 {pg} 页选中异常(尝试{attempt + 1}/3): {sel}, 清弹窗后重选")
                await wait_no_modal(fr, 15)
                await asyncio.sleep(3 * (attempt + 1))
            if not ok:
                log(f"第 {pg} 页重选 3 次仍异常, 放弃本轮")
                return 6
            want = f"已选{n_rows}/{n_rows}"
```

强制重发勾选事件：`select_all_page` 的 `cb.check()` 前提是复选框未勾；「已选0/100」时表头框多半未勾、check() 会发事件，但保险起见在重试轮先 uncheck——把 `select_all_page` 开头 `for attempt in range(3):` 循环前加一行参数（不改签名，加默认参数）：

```python
async def select_all_page(fr, force_recheck=False):
    cb = fr.locator(".ant-table-thead .ant-checkbox-input").first
    if force_recheck:
        try:
            await cb.uncheck(timeout=5000)
        except Exception:
            pass
    for attempt in range(3):
```

重试调用处改为 `sel = await select_all_page(fr, force_recheck=(attempt > 0))`。

- [ ] **Step 4: 跑单测确认通过 + 语法**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_isv_stock_sync -v && ../venv/bin/python -c "import ast;ast.parse(open('isv_stock_sync.py').read())" && echo PARSE_OK
```
Expected: 7 tests PASS + PARSE_OK。

- [ ] **Step 5: 活体验证（onsale 口径前 2 页 dry-run，~2 分钟，不点同步）**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
source chrome_guard.sh && ensure_chrome
../venv/bin/python isv_stock_sync.py --pages 2 --dry-run 2>&1 | tail -6
```
Expected: `[1/9] DRY 已选100/100`、`[2/9] DRY 已选100/100`、`完成: 2 页 × 100 条 (DRY)`。若出现「选中异常(尝试…/3)」日志且第 2/3 次成功=重试路径真实生效（更好）；3 次全败则停下报告（说明还有未知前置坑，勿带病上线）。

---

### Task 6: run_night_window.sh 夜窗链 + stock-refresh plist 改指

**Files:**
- Create: `automation/sourcing/run_night_window.sh`（可执行）
- Modify: `~/Library/LaunchAgents/com.spzx.stock-refresh.plist`
- Modify: `scripts/launchd/com.spzx.stock-refresh.plist`（仓库副本同步）

**Interfaces:**
- Consumes: `run_stock_refresh.sh`、`run_stock_sync.sh`、`chrome_kill.sh`（全部已存在）。
- Produces: 03:00 单触发器链：夜巡 → 库存同步 → 收 Chrome；`DRY=1 bash run_night_window.sh` 只打印不执行（供语法/链路验证）。

- [ ] **Step 1: 写 run_night_window.sh**

```bash
#!/bin/bash
# 夜窗链（spec 2026-10-19-schedule-optimization §3）：03:00 LaunchAgent com.spzx.stock-refresh 触发。
# 夜巡(在售9页快照宇宙, 只读详情页) → ISV库存同步(唯一日常写) → 收9222。
# 串行而非三个定时器：夜巡最坏 2h（fetch 超时 65s×174 页），定时触发会撞死+被守卫跳过。
# 各段自带守卫/台账/告警；链只负责顺序与日志，任一段 rc!=0 不拦后段。
# DRY=1 时只打印计划不执行（链路验证用）。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
LOG=/tmp/night_window.log
if [ -n "${DRY:-}" ]; then
  echo "DRY: sleep $((RANDOM % 300)); run_stock_refresh.sh; run_stock_sync.sh; chrome_kill.sh"
  exit 0
fi
sleep $((RANDOM % 300))
echo "[$(date '+%F %T')] === 夜窗链 开始 ===" >> "$LOG"
bash "$DIR/run_stock_refresh.sh"
echo "[$(date '+%F %T')] 夜巡 rc=$?" >> "$LOG"
bash "$DIR/run_stock_sync.sh"
echo "[$(date '+%F %T')] 同步 rc=$?" >> "$LOG"
bash "$DIR/chrome_kill.sh"
echo "[$(date '+%F %T')] === 夜窗链 结束 ===" >> "$LOG"
```

```bash
chmod +x /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_night_window.sh
bash -n /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_night_window.sh && echo SYNTAX_OK
DRY=1 bash /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_night_window.sh
```
Expected: SYNTAX_OK + `DRY: sleep …` 行。

- [ ] **Step 2: 重写两份 stock-refresh plist（Program 换 run_night_window.sh，注释更新，其余键不变）**

`~/Library/LaunchAgents/com.spzx.stock-refresh.plist` 与 `scripts/launchd/com.spzx.stock-refresh.plist` 写入同一内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- 2026-10-19 改造（spec schedule-optimization §3）：03:00 触发夜窗链 run_night_window.sh =
     夜巡(detect_stock_night) → ISV库存同步(9页) → 收9222。原仅夜巡。另有 19:30 事件驱动补偿
     走 com.spzx.stock-sync → run_stock_event_sync.sh。backfill 建档临时窗口 21:30-02:45 不占此链。
     ⚠️ 读取用 `plutil -extract <kp> xml1 -o - <f>`；裸 `plutil -extract <kp> <fmt> <f>`（不带 -o -）
     会原地覆写（2026-10-08/10-18 两次事故）。写改一律整体重写 XML。 -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spzx.stock-refresh</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_night_window.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>Nice</key>
    <integer>5</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing</string>

    <key>StandardOutPath</key>
    <string>/tmp/stock_refresh_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/stock_refresh_launchd.log</string>
</dict>
</plist>
```

- [ ] **Step 3: lint + 重载 + 核对 + 副本 cmp**

```bash
plutil -lint ~/Library/LaunchAgents/com.spzx.stock-refresh.plist
launchctl bootout gui/$(id -u)/com.spzx.stock-refresh 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.stock-refresh.plist
launchctl print gui/$(id -u)/com.spzx.stock-refresh | grep -A4 "program"
cmp ~/Library/LaunchAgents/com.spzx.stock-refresh.plist /Users/qyk9527/ideaProject/spzx-parent/scripts/launchd/com.spzx.stock-refresh.plist && echo COPIES_SAME
```
Expected: `OK`；program = `run_night_window.sh`；COPIES_SAME。**不要 kickstart**（会立刻真跑夜窗+同步）——首跑=今晚 03:00。

---

### Task 7: 事件判定 stock_event_check.py + run_stock_event_sync.sh + stock-sync plist 改造

**Files:**
- Create: `automation/sourcing/stock_event_check.py`
- Create: `automation/sourcing/run_stock_event_sync.sh`（可执行）
- Test: `automation/sourcing/test_stock_event_check.py`
- Modify: `~/Library/LaunchAgents/com.spzx.stock-sync.plist`
- Modify: `scripts/launchd/com.spzx.stock-sync.plist`

**Interfaces:**
- Produces: `decide(alert_rows, has_success_batch) -> (bool, reason)` 纯函数；CLI `stock_event_check.py` 打印 `EVENT` 或 `NO_EVENT`（exit 0）/异常 exit 1；`run_stock_event_sync.sh --check` 只判定不执行。
- Consumes: `dbconf.DB_CONFIG`（仓库约定 `from dbconf import DB_CONFIG`）；`run_stock_sync.sh`（Task 3 改造版）。

- [ ] **Step 1: 先写失败测试**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decide 纯函数单测（spec 2026-10-19-schedule-optimization §5）"""
import unittest
from stock_event_check import WHITELIST, decide


def rows(*items):
    # items: (alert_type, days_ago)
    import time
    out = []
    for t, d in items:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - d * 86400))
        out.append({"alert_type": t, "status": 0, "create_time": ts})
    return out


class TestDecide(unittest.TestCase):
    def test_today_whitelist_hit(self):
        ok, why = decide(rows(("oversell_risk", 0)), True)
        self.assertTrue(ok)

    def test_old_unread_ignored(self):
        ok, why = decide(rows(("source_dead", 3)), True)
        self.assertFalse(ok)

    def test_non_whitelist_ignored(self):
        ok, why = decide(rows(("ingest_stale", 0)), True)
        self.assertFalse(ok)

    def test_read_alert_ignored(self):
        import time
        r = [{"alert_type": "low_stock", "status": 1,
              "create_time": time.strftime('%Y-%m-%d %H:%M:%S')}]
        ok, why = decide(r, True)
        self.assertFalse(ok)

    def test_no_success_batch_triggers(self):
        ok, why = decide([], False)
        self.assertTrue(ok)

    def test_all_clear(self):
        ok, why = decide([], True)
        self.assertFalse(ok)

    def test_whitelist_members(self):
        self.assertEqual(WHITELIST, {"oversell_risk", "low_stock", "onsale_binding_change",
                                     "onsale_mismatch", "isv_sync_fail", "source_dead"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_stock_event_check -v
```
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 实现 stock_event_check.py**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock_event_check.py — 19:30 事件驱动补偿判定（spec 2026-10-19-schedule-optimization §5）

触发 = 当天新写且未读的库存类 sync_alert（白名单）∪ 今天无 isv_stock_sync success 批次。
限定「当天新写」：陈年未读不触发（否则事件驱动失效）。纯 DB, 不碰 Chrome。
打印 EVENT / NO_EVENT；exit 0=判定完成, 1=判定异常。
"""
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG

WHITELIST = {"oversell_risk", "low_stock", "onsale_binding_change",
             "onsale_mismatch", "isv_sync_fail", "source_dead"}


def decide(alert_rows, has_success_batch):
    """纯函数。alert_rows: [{alert_type,status,create_time}]（create_time 'YYYY-MM-DD HH:MM:SS'）。"""
    today = time.strftime('%Y-%m-%d')
    hits = [r for r in alert_rows
            if r.get("alert_type") in WHITELIST
            and r.get("status") == 0
            and str(r.get("create_time") or "")[:10] == today]
    if hits:
        types = sorted({r["alert_type"] for r in hits})
        return True, f"当天新写库存告警 {len(hits)} 条: {','.join(types)}"
    if not has_success_batch:
        return True, "今日无 isv_stock_sync success 批次（夜窗未跑成）"
    return False, "无库存事件"


def main():
    import pymysql
    conn = pymysql.connect(**DB_CONFIG, charset='utf8mb4')
    try:
        cur = conn.cursor()
        today = time.strftime('%Y-%m-%d')
        cur.execute(
            "SELECT alert_type, status, create_time FROM sync_alert "
            "WHERE DATE(create_time)=%s", (today,))
        rows = [{"alert_type": a, "status": s, "create_time": t} for a, s, t in cur.fetchall()]
        cur.execute(
            "SELECT COUNT(*) FROM ingest_batch "
            "WHERE dataset='isv_stock_sync' AND status='success' AND DATE(create_time)=%s",
            (today,))
        has_ok = cur.fetchone()[0] > 0
        cur.close()
    finally:
        conn.close()
    ok, why = decide(rows, has_ok)
    print("EVENT" if ok else "NO_EVENT")
    print(why)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"CHECK_ERROR {e!r}")
        sys.exit(1)
```

- [ ] **Step 4: 跑单测 + 活体判定**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m unittest test_stock_event_check -v
../venv/bin/python stock_event_check.py; echo "exit=$?"
```
Expected: 7 tests PASS；活体输出今天真实状态（今天 06:00:53 有 isv_sync_fail 未读 → 应 `EVENT`；若 NO_EVENT 也接受——以库里事实为准）。

- [ ] **Step 5: 写 run_stock_event_sync.sh**

```bash
#!/bin/bash
# 19:30 事件驱动补偿（spec 2026-10-19-schedule-optimization §5）。
# 无事件: 一行日志退出, 不拉 Chrome, 不写台账（新鲜度面板无批次属预期, 口径见注册表 remark）。
# 有事件: ensure_chrome+ensure_login → 复用 run_stock_sync.sh（9 页在售口径）。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/stock_event_sync.log
echo "[$(date '+%F %T')] === 事件检查 开始 ===" >> "$LOG"
if [ "${1:-}" = "--check" ]; then
  "$PY" "$DIR/stock_event_check.py"; echo "exit=$?"; exit 0
fi
EV=$("$PY" "$DIR/stock_event_check.py" 2>>"$LOG") || { echo "[$(date '+%F %T')] 判定异常" >> "$LOG"; exit 1; }
if ! echo "$EV" | grep -q "^EVENT$"; then
  echo "[$(date '+%F %T')] $(echo "$EV" | tail -1) → 无库存事件, 不拉 Chrome" >> "$LOG"
  exit 0
fi
echo "[$(date '+%F %T')] $(echo "$EV" | tail -1) → 补跑同步" >> "$LOG"
bash "$DIR/run_stock_sync.sh"
echo "[$(date '+%F %T')] === 事件检查 结束 ===" >> "$LOG"
```

```bash
chmod +x /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_stock_event_sync.sh
bash -n /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_stock_event_sync.sh && echo SYNTAX_OK
bash /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_stock_event_sync.sh --check
```
Expected: SYNTAX_OK + 与 Step 4 相同判定输出。**不带 --check 的整跑留给今晚 19:30 自然触发**（今天真有事件也无妨：12:30 那轮 failed，补跑正好愈合）。

- [ ] **Step 6: 重写两份 stock-sync plist（单时刻 19:30，Program 换 run_stock_event_sync.sh）**

`~/Library/LaunchAgents/com.spzx.stock-sync.plist` 与 `scripts/launchd/com.spzx.stock-sync.plist` 同内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- 2026-10-19 改造（spec schedule-optimization §3/§5）：库存同步写操作收敛——
     日常唯一写在 03:00 夜窗链（com.spzx.stock-refresh → run_night_window.sh 链内 run_stock_sync.sh）；
     本作业 19:30 改为事件驱动补偿（run_stock_event_sync.sh）：当天新写库存类告警或当日无
     success 批次才拉 Chrome 补跑，无事件不拉 Chrome 不写台账。原 05:30/12:30/19:30 三时刻废止。
     ⚠️ 读取用 `plutil -extract <kp> xml1 -o - <f>`；写改一律整体重写 XML。 -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spzx.stock-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/run_stock_event_sync.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>19</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>Nice</key>
    <integer>5</integer>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing</string>

    <key>StandardOutPath</key>
    <string>/tmp/stock_sync_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/stock_sync_launchd.log</string>
</dict>
</plist>
```

- [ ] **Step 7: lint + 重载 + 核对 + 副本 cmp**

```bash
plutil -lint ~/Library/LaunchAgents/com.spzx.stock-sync.plist
launchctl bootout gui/$(id -u)/com.spzx.stock-sync 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.stock-sync.plist
launchctl print gui/$(id -u)/com.spzx.stock-sync | grep -A4 "program"
/usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval' ~/Library/LaunchAgents/com.spzx.stock-sync.plist
cmp ~/Library/LaunchAgents/com.spzx.stock-sync.plist /Users/qyk9527/ideaProject/spzx-parent/scripts/launchd/com.spzx.stock-sync.plist && echo COPIES_SAME
```
Expected: OK；program=run_stock_event_sync.sh；`Dict { Hour = 19, Minute = 30 }`；COPIES_SAME。**不要 kickstart**。

---

### Task 8: chrome-kill / onsale-scan plist 重排 + sycm crontab 重排 + 僵尸清理

**Files:**
- Modify: `~/Library/LaunchAgents/com.spzx.chrome-kill.plist` + `scripts/launchd/` 副本
- Modify: `~/Library/LaunchAgents/com.spzx.onsale-scan.plist` + `scripts/launchd/` 副本
- Modify: crontab（备份→sed→alarm 安装）
- Delete: `~/Library/LaunchAgents/com.spzx.sku-match.plist` + `scripts/launchd/com.spzx.sku-match.plist`

**Interfaces:**
- Produces: 中午窗口 12:06 推广日报 → 12:35 生意参谋 → 12:50 在售扫描 → 13:10 收 Chrome；05:10 收 Chrome 条目删除（夜窗链末尾自收）；周六 collect_full 僵尸行删除；sku-match 残留删除。

- [ ] **Step 1: 备份**

```bash
crontab -l > /tmp/crontab.bak.20261019
cp ~/Library/LaunchAgents/com.spzx.chrome-kill.plist /tmp/chrome-kill.bak.plist
cp ~/Library/LaunchAgents/com.spzx.onsale-scan.plist /tmp/onsale-scan.bak.plist
```

- [ ] **Step 2: 重写两份 chrome-kill plist（单时刻 13:10）**

`~/Library/LaunchAgents/` 与 `scripts/launchd/` 同内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- 窗口外收 9222：13:10（中午窗口尾）。05:10 条目 2026-10-19 删除——夜窗链
     run_night_window.sh 末尾自己收（spec schedule-optimization §3）。
     任务由 chrome_guard.sh ensure_chrome 静默自启，本作业负责「用完即走」的「走」。 -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.spzx.chrome-kill</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/chrome_kill.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>13</integer>
        <key>Minute</key>
        <integer>10</integer>
    </dict>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/chrome_kill_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/chrome_kill_launchd.log</string>
</dict>
</plist>
```

- [ ] **Step 3: 重写两份 onsale-scan plist（12:40 → 12:50，只改 Minute 与注释行）**

XML 同现文件，仅两处：注释首行 `每日 12:40` → `每日 12:50（中午只读窗口第三棒, spec schedule-optimization §3）`；`<key>Minute</key><integer>40</integer>` → `<integer>50</integer>`。其余键（Label/ProgramArguments/EnvironmentVariables/WorkingDirectory/StandardOutPath）逐字保留。

- [ ] **Step 4: lint + 重载 + 核对**

```bash
for l in chrome-kill onsale-scan; do
  plutil -lint ~/Library/LaunchAgents/com.spzx.$l.plist
  launchctl bootout gui/$(id -u)/com.spzx.$l 2>/dev/null
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.spzx.$l.plist
  /usr/libexec/PlistBuddy -c 'Print :StartCalendarInterval' ~/Library/LaunchAgents/com.spzx.$l.plist
  cmp ~/Library/LaunchAgents/com.spzx.$l.plist /Users/qyk9527/ideaProject/spzx-parent/scripts/launchd/com.spzx.$l.plist || echo "COPY_DIFF $l"
done
```
Expected: chrome-kill `Hour = 13 / Minute = 10`；onsale-scan `Hour = 12 / Minute = 50`；无 COPY_DIFF。

- [ ] **Step 5: crontab 重排（sycm 06:00→12:35；删 collect_full；修两条过期注释）**

```bash
crontab -l | sed -e 's|^0 6 \* \* \* /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/cron_sycm_snapshot.sh|35 12 * * * /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/cron_sycm_snapshot.sh|' \
                 -e '/cron_collect_full\.sh/d' \
                 -e 's|^# 库存变化检测(货源销量计算)+提醒, 05:00.*|# 库存提醒检测已并入 db_daily 04:30（inventory_cron 链式调 detect_alerts）|' \
                 -e 's|^# 质量分级(纯DB幂等), 05:30|# 质量分级已并入 db_daily 04:30|' \
                 -e 's|^# 生意参谋商品效果快照(需9222窗口模式, 无守卫则跳过), 每日 06:00|# 生意参谋商品效果快照(需9222窗口模式), 每日 12:35（中午只读窗口第二棒）|' \
                 > /tmp/crontab.new
diff /tmp/crontab.bak.20261019 /tmp/crontab.new
```
人工核对 diff 只含预期 4 处后：

```bash
perl -e 'alarm 20; exec @ARGV' crontab /tmp/crontab.new
crontab -l | grep -n "sycm\|collect_full\|35 12"
```
Expected: diff = sycm 时刻行 + collect_full 行删除 + 两条注释变化；安装后 grep 见 `35 12 * * * …cron_sycm_snapshot.sh`、无 collect_full。⚠️ alarm 触发（安装卡死）= 放弃本次并报告用户，勿重试超过 1 次（回滚 `crontab /tmp/crontab.bak.20261019`）。

- [ ] **Step 6: 删 sku-match 残留**

```bash
launchctl bootout gui/$(id -u)/com.spzx.sku-match 2>/dev/null
rm ~/Library/LaunchAgents/com.spzx.sku-match.plist
rm /Users/qyk9527/ideaProject/spzx-parent/scripts/launchd/com.spzx.sku-match.plist
ls ~/Library/LaunchAgents/ | grep sku-match; echo "exit=$?"
```
Expected: `exit=1`（文件已不在）。

---

### Task 9: cleanup_runtime.sh 磁盘卫生 + db_daily 第 5 步

**Files:**
- Create: `scripts/cleanup_runtime.sh`（可执行，支持 --dry-run）
- Modify: `scripts/db_daily.sh`（末尾 echo 前插第 5 步）
- Modify: `automation/AGENTS.md`（新增纪律条款一行）

**Interfaces:**
- Produces: 每日 04:30 随 db_daily 跑；`--dry-run` 打印将删清单；输出行 `cleanup: del=N free=XKB dry=0|1` 进 /tmp/cleanup_runtime.log。
- 红线内嵌：绝不触碰 chrome-profile*、pdd_images*、novel_batches、douyin_reports、~/Backups/spzx-db/；无任何按扩展名的全域扫描删除。

- [ ] **Step 1: 写 scripts/cleanup_runtime.sh**

```bash
#!/bin/bash
# cleanup_runtime.sh — 磁盘卫生（spec 2026-10-19-schedule-optimization §9），db_daily 第 5 步。
# 1) /tmp spzx 系日志 >2MB 裁尾 2000 行（台账真源在 ingest_batch, 日志中段历史可丢）
# 2) 截图清理：模式白名单 + mtime>7 天（禁止按扩展名全域扫删——pdd_images 输入素材混在图片里）
# 3) /tmp spzx 探针残留 mtime>14 天
# 绝不触碰：chrome-profile*（登录态）/ pdd_images* / novel_batches / douyin_reports / ~/Backups/spzx-db/
# 用法: cleanup_runtime.sh [--dry-run]
P=/Users/qyk9527/ideaProject/spzx-parent
LOG=/tmp/cleanup_runtime.log
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
DEL=0; FREE=0
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

rm_one() {
  local f="$1" s
  s=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "$DRY" = "1" ]; then echo "DRY_DEL $f ($((s / 1024))KB)"; else rm -f "$f"; fi
  DEL=$((DEL + 1)); FREE=$((FREE + s))
}

# 1) 日志裁剪
for f in /tmp/cron_stats.log /tmp/sycm_daily_cron.log /tmp/alimama_promo_cron.log \
         /tmp/stock_sync_cron.log /tmp/stock_refresh_cron.log /tmp/onsale_scan.log \
         /tmp/inventory_cron.log /tmp/inventory_weekly.log /tmp/chrome_kill.log \
         /tmp/backfill_night_run.log /tmp/db_daily.log /tmp/night_window.log \
         /tmp/stock_event_sync.log /tmp/cleanup_runtime.log /tmp/cron_collect_full.log \
         /tmp/sku_match_run.log /tmp/cat_v2_wrap.log /tmp/brand_run.log; do
  [ -f "$f" ] || continue
  sz=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "$sz" -gt 2097152 ]; then
    say "裁剪 $f ($((sz / 1024))KB → 末尾2000行)"
    [ "$DRY" = "0" ] && { tail -n 2000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; }
  fi
done

# 2) 截图（模式白名单 + 7 天）
for f in "$P"/automation/tb-auto/test_screenshot_*.png \
         "$P"/automation/tb-auto/submit_unknown_*.png \
         /tmp/sycm_noapi.png; do
  [ -e "$f" ] || continue
  [ -n "$(find "$f" -mtime +7 2>/dev/null)" ] && rm_one "$f"
done

# 3) /tmp spzx 探针残留（14 天）
for f in /tmp/spzx_* /tmp/noon_* /tmp/sku_direct_probe*; do
  [ -e "$f" ] || continue
  [ -n "$(find "$f" -mtime +14 2>/dev/null)" ] && rm_one "$f"
done

say "=== 清理完成 del=$DEL free=$((FREE / 1024))KB dry=$DRY ==="
echo "cleanup: del=$DEL free=$((FREE / 1024))KB dry=$DRY"
```

- [ ] **Step 2: dry-run 验证**

```bash
chmod +x /Users/qyk9527/ideaProject/spzx-parent/scripts/cleanup_runtime.sh
bash /Users/qyk9527/ideaProject/spzx-parent/scripts/cleanup_runtime.sh --dry-run
tail -2 /tmp/cleanup_runtime.log
```
Expected: 打印 DRY_DEL 行（如有符合条件文件）+ `cleanup: del=N free=XKB dry=1`；日志含 `dry=1`。

- [ ] **Step 3: 真删夹具验证（造 8 天前的假截图 + 15 天前的假探针，跑真删，护住禁区）**

```bash
touch -t $(date -v-8d +%Y%m%d1200) /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/test_screenshot_9999999.png
touch -t $(date -v-15d +%Y%m%d1200) /tmp/spzx_old_probe_test.json
PDD_BEFORE=$(ls /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/pdd_images_1688 | wc -l)
bash /Users/qyk9527/ideaProject/spzx-parent/scripts/cleanup_runtime.sh
ls /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/test_screenshot_9999999.png 2>&1
ls /tmp/spzx_old_probe_test.json 2>&1
PDD_AFTER=$(ls /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/pdd_images_1688 | wc -l)
[ "$PDD_BEFORE" = "$PDD_AFTER" ] && echo PDD_UNTOUCHED
```
Expected: 两个 `No such file`（夹具被删）；PDD_UNTOUCHED；日志 `del=2 … dry=0`。

- [ ] **Step 4: db_daily.sh 加第 5 步（在最后 `=== db_daily 结束 ===` echo 之前插入）**

```bash
# 5) 磁盘卫生（日志裁剪+截图/探针清理, spec schedule-optimization §9; 纯文件操作不碰 Chrome）
bash "$P/scripts/cleanup_runtime.sh" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] cleanup rc=$?" >> "$LOG"
```

```bash
bash -n /Users/qyk9527/ideaProject/spzx-parent/scripts/db_daily.sh && echo SYNTAX_OK
```

- [ ] **Step 5: automation/AGENTS.md 纪律条款（「高价值经验」清单末尾加一条）**

```markdown
- **新增截图/快照落盘点必须登记** `scripts/cleanup_runtime.sh` 的模式白名单（spec schedule-optimization §9），否则视为 bug——磁盘只增不删的教训：auto_list 时间戳截图曾无限累积。
```

---

### Task 10: 注册表/卡片/cron.md 同步 + 一致性门全绿 + 留痕

**Files:**
- Modify: `automation/sourcing/task-progress-config.json`
- Modify: `~/docs/cron.md`
- Modify（SQL）: `ingest_dataset` 注册表 3 行
- Verify: `python3 scripts/check-consistency.py`
- Create: log_work 留痕

- [ ] **Step 1: 注册表核对并更新（先看实际 code 与现值，勿盲 UPDATE）**

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx \
  -e "SELECT dataset_code, cron_expr, LEFT(IFNULL(remark,''),60) FROM ingest_dataset WHERE dataset_code IN ('item_daily_sycm','isv_stock_sync','onsale_scan')"
```

按实际 code 执行（code 与上表不符时先报告再改）：

```sql
UPDATE ingest_dataset SET cron_expr='35 12 * * *' WHERE dataset_code='item_daily_sycm';
UPDATE ingest_dataset SET cron_expr='50 12 * * *' WHERE dataset_code='onsale_scan';
UPDATE ingest_dataset SET cron_expr='45 3 * * *',
  remark=CONCAT(IFNULL(remark,''),' ；2026-10-19 基线=03:00 夜窗链式接续(夜巡后)；19:30 为事件驱动补偿（当天新写库存类告警 ∪ 当日无 success 批次才跑），无事件日无批次属预期，不是漏跑')
  WHERE dataset_code='isv_stock_sync';
```

```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx \
  -e "SELECT dataset_code, cron_expr FROM ingest_dataset WHERE dataset_code IN ('item_daily_sycm','isv_stock_sync','onsale_scan')"
```
Expected: 三行新值。

- [ ] **Step 2: task-progress-config.json 卡片时刻同步**

```bash
grep -n "06:00\|05:30\|12:40\|12:30\|19:30\|13:57\|05:10" /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/task-progress-config.json
```
按命中行把时刻改成对应新值（sycm→12:35、库存同步→03:45 夜窗链+19:30 事件补偿、在售扫描→12:50、收 Chrome→13:10），JSON 改后必须 `../venv/bin/python -c "import json;json.load(open('automation/sourcing/task-progress-config.json'))" && echo JSON_OK`。

- [ ] **Step 3: ~/docs/cron.md 八模块速查表按新时刻更新**

对照 spec §3 时刻表逐行改（backfill 行标注「临时，完成自退」；补 19:30 事件驱动与 04:30 cleanup 第 5 步说明）。

- [ ] **Step 4: 一致性门**

```bash
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/check-consistency.py
```
Expected: 退出码 0。若报漂移：按报错逐条修（优先改注册表/卡片对齐机器事实；机器侧 plist/crontab 以本计划为准勿反向改）；修到全绿为止，修不动=报告用户。

- [ ] **Step 5: 全量单测回归**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
../venv/bin/python -m unittest test_login_wall test_stock_event_check test_isv_stock_sync -v
../venv/bin/python -m unittest test_sync_onsale -v 2>&1 | tail -3
```
Expected: 全 PASS（新 3 个测试类 + 存量 test_sync_onsale 不回归）。

- [ ] **Step 6: 上线检查单 + 留痕**

```bash
launchctl list | grep spzx            # 6 个 Agent 全 loaded（sku-match 消失）
crontab -l | grep -c "^\#"            # 行数与预期对照
bash /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/test_chrome_guard.sh
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/log_work.py --module 系统 \
  --title "调度体系优化A方案落地：夜窗链+事件驱动+守卫四件套+磁盘卫生" \
  --progress "任务10个, 测试17新增, 门全绿"
```

---

## 上线后观察（今晚起，非任务）

| 时点 | 看什么 | 位置 |
|------|--------|------|
| 今晚 ~23:30 | backfill 夜1 结束待建档=0 自退 | `…/backfill_nights.log` |
| 明 03:00-04:00 | 夜窗链顺序：夜巡 SUMMARY → 同步 rc=0 rows≈4000 → 已收 9222 | `/tmp/stock_refresh_cron.log`、`/tmp/stock_sync_cron.log`、`/tmp/chrome_kill.log`、`/tmp/night_window.log` |
| 明 12:06/12:35/12:50 | 三棒依次跑、互不 skip；alimama 回补 10-17~10-19 断档 | 各自 cron 日志 |
| 明 13:10 | 收 Chrome | `/tmp/chrome_kill.log` |
| 明 19:30 | 事件判定与（若有事件）补跑 | `/tmp/stock_event_sync.log` |
| 后天起 | sync_alert 不再出现同 key 连续「其他采集任务在跑」 | 后台告警页 |
