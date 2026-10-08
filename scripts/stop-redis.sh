#!/usr/bin/env bash
# 本机 Redis 停止。由 ~/Desktop/Redis开关.command 调用。
#
# 为什么这里要"先算影响、再要一句确认"，而 Nacos 那种直接停不行：
#  1) 6379 是**这台机器共享的**，不是 spzx 一个项目的。2026-10-08 实测挂着 54 个连接、
#     3 个 java 进程（本机另外几个 Spring Boot 项目的后端与正在跑的测试），
#     db0/db1/db9 里 959 个键全是登录令牌（auth:refresh_token:* / prefix_user_token_*）。
#     停的那几秒里这些进程的操作会直接报错。
#  2) 持久化只有 RDB（appendonly no），save 规则是 3600/1、300/100、60/10000。
#     SIGTERM 正常退出会落一次盘，但**上一次落盘之后的写入可能丢**——
#     实测停前 rdb_changes_since_last_save=125，也就是有 125 处变更只活在内存里。
#  3) 归 launchd 管（KeepAlive=true），所以只有 `brew services stop` 停得住；
#     kill 会被立刻复活。停完还要再等几秒复查端口，确认不是"杀了又起来了"这种假成功。
set -u

PORT=6379
SERVICE=redis

say() { printf '%s\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

AUTO_YES=0
case "${1:-}" in (-y|--yes) AUTO_YES=1 ;; esac

BREW="$(command -v brew || true)"
[ -n "$BREW" ] || die "没找到 brew。"
PREFIX="$("$BREW" --prefix "$SERVICE" 2>/dev/null || true)"
REDIS_CLI="${PREFIX:-}/bin/redis-cli"

listening() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2; }
redis_ping() { [ -x "$REDIS_CLI" ] && "$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 ping 2>/dev/null; }

LISTENER="$(listening)"
if [ -z "$LISTENER" ]; then
  say "=== 端口 $PORT 没人听 → Redis 本来就没在跑，无事可做 ==="
  say "要起来：双击 ~/Desktop/Redis开关.command"
  exit 0
fi
# 端口在听但应答不像 Redis：这是别人占的端口，不归本脚本停
if [ "$(redis_ping)" != "PONG" ]; then
  say "=== 端口 $PORT 有人听，但 PING 没回 PONG → 不是 Redis，本脚本不动它 ==="
  printf '%s\n' "$LISTENER" | sed 's/^/  /'
  exit 1
fi

# ── 影响面：把"停了会打断谁"算出来给人看 ──
CLIENTS="$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 info clients 2>/dev/null | awk -F: '/connected_clients/{gsub(/\r/,"",$2); print $2}')"
CHANGES="$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 info persistence 2>/dev/null | awk -F: '/rdb_changes_since_last_save/{gsub(/\r/,"",$2); print $2}')"
say "=== 停 Redis 的影响（$PORT）==="
say "  正在连接的客户端：${CLIENTS:-未知} 个"
say "  只活在内存里、还没落盘的变更：${CHANGES:-未知} 处（save 规则 60s/10000、300s/100、3600s/1）"
say "  连着它的本地进程："
lsof -nP -iTCP -sTCP:ESTABLISHED 2>/dev/null | awk -v p=":$PORT" '$9 ~ p"$" {print $1" pid="$2}' | sort -u | sed 's/^/    /' | head -10

if [ "$AUTO_YES" != 1 ]; then
  if [ ! -t 0 ]; then
    die "非交互环境（没有 tty）就不擅自停共享服务。确认要停请加 --yes。"
  fi
  printf '确认停止 Redis？输入 y 回车：'
  read -r REPLY
  case "$REPLY" in (y|Y|yes|YES) : ;; (*) say "已取消，Redis 原样在跑。"; exit 0 ;; esac
fi

RDB_DIR="$("$REDIS_CLI" -h 127.0.0.1 -p "$PORT" -t 2 config get dir 2>/dev/null | tail -1 | tr -d '\r')"
RDB="$RDB_DIR/dump.rdb"
RDB_BEFORE="$(stat -f %m "$RDB" 2>/dev/null || echo 0)"

say "brew services stop $SERVICE"
"$BREW" services stop "$SERVICE" || die "brew services stop $SERVICE 失败。"

# 等端口真的关掉（SIGTERM 正常退出会先落一次 RDB，可能要一两秒）
DOWN=0
for _ in $(seq 1 20); do
  [ -z "$(listening)" ] && DOWN=1 && break
  sleep 0.5
done
[ "$DOWN" = 1 ] || die "10 秒了端口还在听，没停住。看 brew services info $SERVICE。"

# 复查：KeepAlive 要是还挂着，launchd 会在这里把它拉回来——那就不算停
sleep 3
if [ -n "$(listening)" ]; then
  say "✗ 端口又有人听了：launchd 把它拉回来了，说明这次停没生效。"
  printf '%s\n' "$(listening)" | sed 's/^/  /'
  die "检查 ~/Library/LaunchAgents/homebrew.mxcl.$SERVICE.plist 是不是还在被加载：launchctl list | grep $SERVICE"
fi

RDB_AFTER="$(stat -f %m "$RDB" 2>/dev/null || echo 0)"
say "=== 已停止：$PORT 空着，且 3 秒后没被 launchd 拉回来 ==="
if [ "$RDB_AFTER" -gt "$RDB_BEFORE" ]; then
  say "  退出时落了新快照：$RDB（$(stat -f '%z 字节，%Sm' "$RDB" 2>/dev/null)）"
else
  say "  没落新快照（退出前没有待落盘变更，或落盘被跳过）：$RDB 仍是 $(stat -f %Sm "$RDB" 2>/dev/null)"
fi
say ""
say "顺带把语义说白（这段抄自 brew services --help 原文，不是我推测的）："
say "  stop  = 立刻停 + **注销开机/登录自启** → 下次开机它不会自己起来"
say "  start = 立刻起 + 注册自启（scripts/start-redis.sh 走的就是这条）"
say "  kill  = 只停、保留注册——这份 plist 带 KeepAlive，所以 kill 会被原地复活，别拿它当停服"
say "要再起来：再双击本文件一次，或 scripts/start-redis.sh"
exit 0
