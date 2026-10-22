#!/usr/bin/env bash
# 本机 Redis 启动。由 ~/Desktop/Redis开关.command 调用，也可以直接命令行跑。
#
# 四条判据，改之前先读：
#  1) 这台机器上的 Redis **归 launchd 管**：~/Library/LaunchAgents/homebrew.mxcl.redis.plist
#     里 RunAtLoad 与 KeepAlive 都是 true（实测进程 PPID=1、连续跑了 5 天多）。
#     所以起停用 `brew services start/stop`，别自己 `redis-server --daemonize yes`——
#     手起的那个会占住 6379，launchd 的则在旁边反复复活重试，变成两个主人。
#     同理 stop-local 那边绝不能拿 kill 当停服手段：KeepAlive 会在毫秒级把它拉回来。
#  2) 幂等且不打扰：端口有人听 + PING 回 PONG 就算「已经在跑」，**不重启**。
#     2026-10-08 实测 6379 上有 54 个连接、3 个 java 进程（本机几个项目的后端/测试）
#     正挂着登录令牌，重启一次等于把它们全打断。
#  3) 成功判据是 PONG，不是端口在听。只把端口起来、Redis 还在加载或起不来，都不算成功。
#  4) 端口探测只能用 lsof：curl 127.0.0.1:6379 会拿到 HTTP 400 之类的怪结果，判不出健康。
set -u

# 只留常量、故意不做成参数：这台机器上 Redis 就一个实例、就在 6379。
# （留一个 SPZX_REDIS_PORT 旋钮的坏处是改了端口忘了改服务名，
#   本来想试沙盒、结果 brew services stop 打到真服务上。）
PORT=6379
SERVICE=redis
LOG="$(brew --prefix 2>/dev/null || echo /opt/homebrew)/var/log/${SERVICE}.log"

say() { printf '%s\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

BREW="$(command -v brew || true)"
[ -n "$BREW" ] || die "没找到 brew。这台机器的约定是原生安装（不用 Docker），先装 Homebrew 再双击。"

PREFIX="$("$BREW" --prefix "$SERVICE" 2>/dev/null || true)"
REDIS_CLI="${PREFIX:-}/bin/redis-cli"
REDIS_SERVER="${PREFIX:-}/bin/redis-server"

# 没装过就装（他要求的是"本机有 redis 可用"，缺二进制属于没达成）
if [ ! -x "$REDIS_SERVER" ]; then
  say "$SERVICE 还没装 → 正在 brew install ${SERVICE}（要走外网下载，几秒到十几秒）"
  "$BREW" install "$SERVICE" || die "brew install $SERVICE 失败，看上面 brew 的输出。"
  PREFIX="$("$BREW" --prefix "$SERVICE" 2>/dev/null || true)"
  REDIS_CLI="${PREFIX:-}/bin/redis-cli"
  REDIS_SERVER="${PREFIX:-}/bin/redis-server"
  [ -x "$REDIS_CLI" ] || die "装完了却没找到 redis-cli，brew 的安装前缀变了，看 brew info ${SERVICE}。"
fi

# 兜底：brew 前缀里没有可执行的 redis-cli 时退回 PATH 里的那个。
# 不兜的话 redis_ping 恒失败，会把"已经在跑"误判成"端口被别的东西占着"而拒绝服务。
if [ ! -x "$REDIS_CLI" ]; then
  REDIS_CLI="$(command -v redis-cli || true)"
  [ -n "$REDIS_CLI" ] || die "找不到可执行的 redis-cli（brew 前缀和 PATH 里都没有）。"
fi

redis_ping() { "$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 ping 2>/dev/null; }
listening()  { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2; }

LISTENER="$(listening)"
if [ -n "$LISTENER" ]; then
  if [ "$(redis_ping)" = "PONG" ]; then
    PIDS="$(printf '%s\n' "$LISTENER" | awk '{print $2}' | sort -u | tr '\n' ' ')"
    say "=== Redis 已经在跑，本次不做任何改动（端口 $PORT 有人听、PING 回 PONG）==="
    ps -o pid,rss,etime,command -p $(printf '%s' "$PIDS" | tr ' ' ',' | sed 's/,$//') 2>/dev/null | sed 's/^/  /'
    say "  内存占用：$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 info memory 2>/dev/null | awk -F: '/used_memory_human/{gsub(/\r/,"",$2); print $2}')"
    say "  已连着：$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 info clients 2>/dev/null | awk -F: '/connected_clients/{gsub(/\r/,"",$2); print $2}') 个客户端"
    say ""
    say "要重启（会打断上面这些连接，先想清楚）：$BREW services restart $SERVICE"
    exit 0
  fi
  # 端口被人占着、应答的却不是 Redis：绝不能"顺手"杀它
  say "=== 端口 $PORT 有人听，但 PING 没回 PONG → 不是（或不是健康的）Redis ==="
  printf '%s\n' "$LISTENER" | sed 's/^/  /'
  die "占着 $PORT 的是上面这个进程，本脚本不 kill 不是自己起的进程。腾出 6379 再双击。"
fi

say "=== 端口 $PORT 空着 → 交给 launchd 起（brew services start ${SERVICE}）==="
"$BREW" services start "$SERVICE" || die "brew services start $SERVICE 失败，看 $LOG 最后几行。"

# 起来要时间：等 PONG，最多 15 秒
for _ in $(seq 1 30); do
  [ "$(redis_ping)" = "PONG" ] && break
  sleep 0.5
done
[ "$(redis_ping)" = "PONG" ] || die "15 秒了 PING 还回不来。看 $LOG 最后 20 行：
$(tail -20 "$LOG" 2>/dev/null)"

say "已就绪：$(redis_ping) @127.0.0.1:$PORT"
say "  配置 $PREFIX/etc/$SERVICE.conf ｜ 数据 $("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 config get dir 2>/dev/null | tail -1)"
KEYS=0
for d in 0 1 2 3 4 5 6 7 8 9; do
  n=$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 -n "$d" dbsize 2>/dev/null | tr -d '\r')
  case "$n" in (*[!0-9]* | "") continue ;; esac
  KEYS=$((KEYS + n))
done
say "  现有键 $KEYS 个（RDB 里带回来的，登录态还在）"
say ""
say "要停：再双击本文件一次，或跑 scripts/stop-redis.sh"
exit 0
