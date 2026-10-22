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
