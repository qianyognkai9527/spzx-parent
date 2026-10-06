#!/usr/bin/env bash
# 停掉 start-local.sh 起来的那两个进程。只认 $RUN/pids 里登记过的 pid，且命令行必须还对得上——
# 端口被别人占着（IDEA 起的后端、手动 npm run dev）一律不动，只报告。
set -u

REPO="$HOME/ideaProject/spzx-parent"
WEB="$HOME/webstormProject/spzx-admin"
RUN="$HOME/Library/Application Support/spzx-local"
PIDS="$RUN/pids"
BPORT=8501
FPORT=3001

listener() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }
say() { printf '%b\n' "$*"; }

stop_one() { # stop_one <name> <pid> <cmdline必须包含>
  local name=$1 pid=$2 want=$3 cmd
  cmd="$(ps -o command= -p "$pid" 2>/dev/null)"
  if [ -z "$cmd" ]; then say "  $name pid $pid 已经不在了"; return 0; fi
  case "$cmd" in
    *"$want"*) ;;
    *) say "  \033[31m$name pid $pid 命令行对不上（可能是 pid 被复用了），不动它\033[0m"; return 1 ;;
  esac
  say "  $name pid $pid → SIGTERM"
  kill -TERM "$pid" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    kill -0 "$pid" 2>/dev/null || { say "  $name 已退出"; return 0; }
    sleep 1
  done
  say "  $name 15s 没退（Spring shutdown hook 卡住了？）→ SIGKILL"
  kill -9 "$pid" 2>/dev/null
  return 0
}

say() { printf '%b\n' "$*"; }

say "=== 停止本脚本登记过的进程 ==="
if [ ! -s "$PIDS" ]; then
  say "  没有登记记录（$PIDS 是空的）——本来就没有本脚本起的进程。"
else
  hit=0
  while read -r name pid; do
    [ -n "${pid:-}" ] || continue
    hit=1
    case "$name" in
      backend)  stop_one "后端" "$pid" "spzx-manager.jar" ;;
      frontend) stop_one "前端" "$pid" "vite/bin/vite.js" ;;
    esac
  done < "$PIDS"
  [ "$hit" = 1 ] || say "  登记文件里没有有效 pid"
  : > "$PIDS"
fi

say ""
say "=== 现在还在听的人（不由本脚本管）==="
for p in "$BPORT" "$FPORT"; do
  pid="$(listener "$p")"
  if [ -n "$pid" ]; then
    say "  :$p 仍被 pid $pid 占着 —— $(ps -o command= -p "$pid" 2>/dev/null | cut -c1-90)…"
  else
    say "  :$p 空闲"
  fi
done
say "  （不是本脚本起的后端，要在它自己的启动方式里停：IDEA 的 Run 窗口 / 那个 mvn spring-boot:run 终端。）"
