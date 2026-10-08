#!/usr/bin/env bash
# start-redis.sh / stop-redis.sh 的沙盒夹具。
#
# 为什么要这么麻烦：6379 在这台机器上是**共享**实例（本机另外几个项目的后端正挂着登录令牌），
# 拿它试"停"这条路本身就是一次事故演练。所以这里用 PATH 里塞一个假 brew 的办法，
# 把两个脚本从判据到落盘**整条路径**跑一遍，真 6379 全程没被碰过。
#
# 假 brew 只实现脚本真用到的那几个子命令（--prefix / services start / services stop），
# start/stop 落到 6399 上的一个独立实例（数据目录在 /tmp，用后即删）。
#
# 覆盖的判据（第 5 条是这组夹具存在的理由）：
#   1 端口空着        → 交给 launchd 起，等到 PONG 才算成功
#   2 已经在跑        → 原样复用，**一次 brew services start 都不许发**（否则就是拿重启当启动）
#   3 端口被非 Redis 占 → 拒绝并说明，绝不 kill 别人
#   4 没有 tty 又要停  → 不擅自停共享服务，直接退出，实例必须还活着
#   5 停完了          → 端口关掉 + 3 秒复查；如果 launchd 把它拉回来，必须报"没停住"而不是"已停止"
#   6 退出落盘        → RDB 变新就报"落了新快照"
#
# 不覆盖的（只有真机那一次才证得了，需要单独授权）：`brew services stop redis` 到底
# 会不会把 launchd 的 job 卸掉、下次登录还起不起。夹具里那是假 brew，说了不算。
set -u

PORT=6399
SBX="${TMPDIR:-/tmp}/redis-toggle-sbx"
STATE="$SBX/state"
REPO="$(cd "$(dirname "$0")" && pwd)"
BREW_REAL="$(command -v brew || true)"
R_PREFIX="$("${BREW_REAL:-brew}" --prefix redis 2>/dev/null || echo /opt/homebrew/opt/redis)"
RSERVER="$R_PREFIX/bin/redis-server"
RCLI="$R_PREFIX/bin/redis-cli"
[ -x "$RSERVER" ] || { echo "夹具跑不起来：没有 $RSERVER"; exit 1; }

pass=0; fail=0
ok()  { printf 'ok   %s\n' "$1"; pass=$((pass+1)); }
bad() { printf 'FAIL %s\n' "$1"; fail=$((fail+1)); }

probe() { "$RCLI" -h 127.0.0.1 -p "$PORT" -t 2 ping 2>/dev/null; }
port_pid() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $2}' | head -1; }

cleanup() {
  local pid; pid="$(port_pid)"
  [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null
  [ -n "${HTTPD_PID:-}" ] && kill "$HTTPD_PID" 2>/dev/null
  rm -rf "$SBX"
}
trap cleanup EXIT

rm -rf "$SBX"; mkdir -p "$STATE"

# ── 假 brew ──
FAKEBIN="$SBX/bin"; mkdir -p "$FAKEBIN"
cat > "$FAKEBIN/brew" <<EOF
#!/usr/bin/env bash
set -u
SBX='$SBX'; PORT=$PORT; RSERVER='$RSERVER'
case "\$1" in
  --prefix)
    if [ \$# -ge 2 ]; then echo '$R_PREFIX'; else echo '/opt/homebrew'; fi ;;
  services)
    case "\$2" in
      start)
        echo start >> '$STATE/calls'
        # 夹具开关：放着 noop 就模拟"launchd 收了命令但根本没把服务起来"，
        # 用来证明第 1 条是差分判据（红灯能报、绿灯才算数）
        if [ ! -f '$STATE/noop' ]; then
          "\$RSERVER" --port \$PORT --bind 127.0.0.1 --daemonize yes \\
            --dir "\$SBX" --save '3600 1 300 100 60 10000' --logfile "\$SBX/sbx.log"
        fi ;;
      stop)
        echo stop >> '$STATE/calls'
        pid=\$(lsof -nP -iTCP:\$PORT -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print \$2}' | head -1)
        [ -n "\$pid" ] && kill -TERM "\$pid"
        # 夹具开关：放着这个文件就模拟"KeepAlive 没被卸掉 → 1 秒后原地复活"
        if [ -f '$STATE/respawn' ]; then
          ( sleep 1; "\$RSERVER" --port \$PORT --bind 127.0.0.1 --daemonize yes \\
              --dir "\$SBX" --save '3600 1 300 100 60 10000' --logfile "\$SBX/sbx.log" ) &
        fi ;;
      *) echo "fake brew: 不支持的服务子命令 \$2" >&2; exit 1 ;;
    esac ;;
  *) echo "fake brew: 不支持 \$*" >&2; exit 1 ;;
esac
EOF
chmod +x "$FAKEBIN/brew"

# ── 被测脚本的沙盒副本（只改端口这一处）──
for s in start stop; do
  sed "s/^PORT=6379$/PORT=$PORT/" "$REPO/$s-redis.sh" > "$SBX/$s-redis.sh" || exit 1
  chmod +x "$SBX/$s-redis.sh"
done
export PATH="$FAKEBIN:$PATH"

run_sb() { # <start|stop> [args...] → 输出进 OUT，rc 进 RC
  local which=$1; shift
  OUT="$(bash "$SBX/$which-redis.sh" "$@" 2>&1)"; RC=$?
}

# ══ 1. 端口空着 → 先证判据是红的（launchd 收了命令但没起来），再证它是绿的 ══
[ -z "$(port_pid)" ] || bad "前置条件：$PORT 应该空着"
touch "$STATE/noop"
run_sb start
echo "$OUT" | grep -q "PING 还回不来" && [ "$RC" = 1 ] && [ -z "$(port_pid)" ] \
  && ok "1a 起了却没应答 → 判成失败（这条红，第 1 条的绿才不是白给的）" || bad "1a 空起动应报失败：rc=$RC out=[$OUT]"
rm -f "$STATE/noop"

run_sb start
echo "$OUT" | grep -q "已就绪" && [ "$RC" = 0 ] && [ "$(probe)" = PONG ] \
  && ok "1b 空端口 → 经 launchd 起来并报 PONG" || bad "1b 空端口起动：rc=$RC out=[$OUT]"
[ "$(grep -c start "$STATE/calls" 2>/dev/null)" = 2 ] \
  && ok "1c 两次起动各发 1 次 brew services start（ noop 那次也发了，判据只管结果）" \
  || bad "1c start 调用次数=$(grep -c start "$STATE/calls" 2>/dev/null)，应为 2"

# ══ 2. 已经在跑 → 复用，不许再发 start（拿重启当启动就是事故）══
BEFORE=$(grep -c start "$STATE/calls")
"$RCLI" -p "$PORT" set sbx:probe hello >/dev/null 2>&1
run_sb start
echo "$OUT" | grep -q "已经在跑，本次不做任何改动" && [ "$RC" = 0 ] \
  && [ "$(grep -c start "$STATE/calls")" = "$BEFORE" ] && [ "$("$RCLI" -p "$PORT" get sbx:probe 2>/dev/null)" = "hello" ] \
  && ok "2 在跑时再点一次 → 原样复用、零 start 调用、键还在" || bad "2 幂等：rc=$RC out=[$OUT]"

# ══ 3. 端口被非 Redis 占 → 拒绝且不 kill ══
kill -TERM "$(port_pid)"; sleep 1
/usr/bin/python3 -m http.server "$PORT" --bind 127.0.0.1 >"$SBX/httpd.log" 2>&1 &
HTTPD_PID=$!
sleep 1
run_sb start
echo "$OUT" | grep -q "不是（或不是健康的）Redis" && [ "$RC" = 1 ] && kill -0 "$HTTPD_PID" 2>/dev/null \
  && ok "3 非 Redis 占端口 → 报明原因、退出 1、没动那个进程" || bad "3 端口被占：rc=$RC out=[$OUT] httpd=$(kill -0 $HTTPD_PID 2>/dev/null && echo alive || echo dead)"
kill "$HTTPD_PID" 2>/dev/null; wait "$HTTPD_PID" 2>/dev/null; HTTPD_PID=""

# ══ 4. 没有 tty 又要停 → 不擅自停，实例必须还活着 ══
"$RSERVER" --port "$PORT" --bind 127.0.0.1 --daemonize yes --dir "$SBX" \
  --save '3600 1 300 100 60 10000' --logfile "$SBX/sbx.log"
sleep 1
OUT="$(bash "$SBX/stop-redis.sh" < /dev/null 2>&1)"; RC=$?
echo "$OUT" | grep -q "不擅自停共享服务" && [ "$RC" = 1 ] && [ "$(probe)" = PONG ] \
  && ok "4 非交互环境 → 拒绝停服，Redis 原样在跑" || bad "4 tty 闸门：rc=$RC out=[$OUT]"

# ══ 5a. launchd 没卸掉 → 复活必须被抓住，不能报"已停止" ══
touch "$STATE/respawn"
run_sb stop --yes
echo "$OUT" | grep -q "launchd 把它拉回来了" && [ "$RC" = 1 ] && [ "$(probe)" = PONG ] \
  && ok "5a 杀了又起来 → 判成'没停住'（这条红了就等于脚本在说谎）" || bad "5a 复活判据：rc=$RC out=[$OUT]"
rm -f "$STATE/respawn"

# ══ 5b + 6. 正常停 → 端口关掉、3 秒没复活、退出落了新快照 ══
run_sb stop --yes
echo "$OUT" | grep -q "已停止" && [ "$RC" = 0 ] && [ -z "$(port_pid)" ] && [ -z "$(probe)" ] \
  && ok "5b 正常停 → 端口空着且没被复活" || bad "5b 正常停：rc=$RC out=[$OUT]"
echo "$OUT" | grep -q "退出时落了新快照" \
  && ok "6 退出前落盘 → 报出 dump.rdb 变大" || bad "6 落盘判据：out=[$OUT]"

printf '\n%d 项通过 / %d 项失败\n' "$pass" "$fail"
[ "$fail" = 0 ] || exit 1
exit 0
