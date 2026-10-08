#!/usr/bin/env bash
# spzx 本机前后端启动（资源友好版）。由 ~/Desktop/运营后台开关.command 调用。
#
# 三条设计约束，改脚本前先读：
#  1) 幂等且不自作聪明：端口有人听就复用，**绝不 kill 不是本脚本起的进程**（后端常驻是 IDEA 起的）。
#  2) 省内存优先：JVM 堆封顶 640m + SerialGC + TieredStopAtLevel=1；前端直接起 vite（跳过 npm 包装进程）；
#     **不启动 Docker Desktop**（约 1GB），代价是 MinIO 没起 → 文件上传类功能会报错。
#  3) 成功判据只有两条：端口在听 + 启动日志里没有致命错误。启动慢不算失败，超时报错也不算成功。
#     端口探测只能用 lsof：vite 默认只绑 [::1]（IPv6 localhost），curl 127.0.0.1 会假报连不上。
set -u

REPO="$HOME/ideaProject/spzx-parent"
WEB="$HOME/webstormProject/spzx-admin"
RUN="$HOME/Library/Application Support/spzx-local"
JAR="$REPO/spzx-manager/target/spzx-manager.jar"
PIDS="$RUN/pids"
BLOG="$RUN/backend.log"
FLOG="$RUN/frontend.log"
BPORT=8501
FPORT=3001
MVN_BIN="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin"

mkdir -p "$RUN"
: > "$PIDS"

say() { printf '%s\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# macOS 上让进程活过"关窗口"要两件事，缺一不可（2026-10-06 各测过一次反例）：
#  1) 脱离控制终端：start_new_session=True，否则窗口关闭时内核发给前台进程组的 SIGHUP 会命中它（ps -o tty= 应为 ??）。
#     光有这条还不够：显式对进程组 `kill -HUP` 实测照样打死 JVM。
#  2) 把 SIGHUP 置为忽略：HotSpot 只接管 SIGINT/SIGTERM，SIGHUP 的 SIG_IGN 会穿过 execve 保留下来，
#     实测 nohup 那份对单进程 kill -HUP 能活。
# 不要图省事加 -Xrs：那会让 SIGTERM 也跳过 shutdown hook，stop-local.sh 就优雅不掉它了。
spawn() { # spawn <日志文件> <工作目录> <命令...>  → stdout 打印子进程 pid
  local log=$1 cwd=$2
  shift 2
  # 继承来的代理要是没人监听，子进程所有外网请求都会 Connection refused，
  # 而界面只显示"脚本执行失败"（2026-10-07 00:39 主图重算就是这么挂的：那次后端
  # 从带 http_proxy=127.0.0.1:18080 的会话里起，代理进程早退了）。起之前探一次，
  # 不通就摘掉并说明。警告必须走 stderr——本函数 stdout 只准吐 pid。
  local v hp
  for v in http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY; do
    eval "hp=\${$v:-}"   # 本机 bash 3.2，不用 ${!v} 间接展开
    [ -z "$hp" ] && continue
    if ! python3 -c '
import socket, sys, re
m = re.search(r"([^:/]+):(\d+)/?$", sys.argv[1])
if not m:
    sys.exit(1)
try:
    socket.create_connection((m.group(1), int(m.group(2))), timeout=1).close()
except Exception:
    sys.exit(1)
' "$hp"; then
      printf '  %s=%s 连不上 → 已从子进程环境里摘掉（留着只会让外网请求全失败）\n' "$v" "$hp" >&2
      unset "$v"
    fi
  done
  /usr/bin/python3 - "$log" "$cwd" "$@" <<'PY'
import signal, subprocess, sys
log, cwd, cmd = sys.argv[1], sys.argv[2], sys.argv[3:]
fd = open(log, "ab")
signal.signal(signal.SIGHUP, signal.SIG_IGN)
p = subprocess.Popen(cmd, cwd=cwd, stdout=fd, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
print(p.pid)
PY
}

listener() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }

# 等端口起来；期间发现目标 pid 已退出就立刻返回，别白等 180 秒
wait_port() { # wait_port <port> <deadline_sec> <owned_pid|->
  local port=$1 sec=$2 pid=$3 i=0
  while [ $i -lt "$sec" ]; do
    [ -n "$(listener "$port")" ] && return 0
    if [ "$pid" != "-" ] && ! kill -0 "$pid" 2>/dev/null; then
      say "  进程 $pid 已退出，端口 $port 不会来了"
      return 1
    fi
    sleep 1; i=$((i + 1))
  done
  return 1
}

say "=== [1/4] 依赖检查 ==="
if ! nc -z -w 2 127.0.0.1 3306 2>/dev/null; then
  die "MySQL 3306 没在听。它是原生 LaunchDaemon，起法（要管理员密码）：
   sudo launchctl load -w /Library/LaunchDaemons/com.oracle.oss.mysql.mysqld.plist
   后端没有库会在启动阶段直接失败，所以这里不出手。"
fi
say "  MySQL 3306  ok"
if ! nc -z -w 2 127.0.0.1 6379 2>/dev/null; then
  say "  Redis 6379  没在听 → brew services start redis"
  brew services start redis >/dev/null 2>&1 || die "Redis 起不来，手动看：brew services start redis"
  for _ in 1 2 3 4 5 6 7 8 9 10; do nc -z -w 1 127.0.0.1 6379 2>/dev/null && break; sleep 1; done
fi
nc -z -w 2 127.0.0.1 6379 2>/dev/null || die "Redis 还是没起来"
say "  Redis 6379  ok"
if nc -z -w 1 127.0.0.1 9000 2>/dev/null; then
  say "  MinIO 9000  ok（Docker 已在跑）"
else
  say "  MinIO 9000  跳过 —— 本脚本不启动 Docker Desktop（省约 1GB）。上传/图片相关功能会报错，其余不受影响。"
fi

say ""
say "=== [2/4] 后端 :$BPORT ==="
JAVA_HOME_DIR="$(/usr/libexec/java_home -v 21 2>/dev/null || true)"
[ -n "$JAVA_HOME_DIR" ] || die "找不到 JDK 21（/usr/libexec/java_home -v 21 无输出）"
JAVA_BIN="$JAVA_HOME_DIR/bin/java"

bp="$(listener "$BPORT")"
if [ -n "$bp" ]; then
  say "  已经有人在听（pid ${bp}）→ 复用，不动它"
  [ "$(ps -o command= -p "$bp" 2>/dev/null | grep -c 'target/classes')" != "0" ] && \
    say "  注意：这个进程吃的是 target/classes（IDEA 或 mvn spring-boot:run 起的）。改完 Java 代码要在它自己的启动方式里重启才生效，本脚本管不到它。"
else
  # 只比运行期源码：src/test 下有 165 个文件比 jar 新，但测试代码不进 jar，为它打包是白等两分钟
  newest_src="$(find "$REPO/spzx-manager/src/main" "$REPO/spzx-model/src/main" "$REPO/spzx-common" \
      \( -name '*.java' -o -name '*.yml' -o -name '*.xml' \) ! -path '*/target/*' -newer "$JAR" -print 2>/dev/null | head -1)"
  # 删掉的源文件不会让任何**现存**文件变新，光比 mtime 会拿旧 jar 起（旧 jar 里那些类还在，
  # 端点照旧能通，验的却不是你眼前的代码）。2026-10-07 删死模块当场踩到，让 git 来报删除。
  deleted_src="$(cd "$REPO" && git status --porcelain 2>/dev/null \
      | awk '$1=="D" && $2 ~ /src\/main\/.*\.(java|yml|xml)$/ {print $2; exit}')"
  if [ ! -f "$JAR" ] || [ -n "$newest_src" ] || [ -n "$deleted_src" ]; then
    say "  jar 缺失或落后于源码（比 ${JAR} 新的源文件：${newest_src:-无}；被删的源文件：${deleted_src:-无}）→ 打包"
    if pgrep -f "$MVN_BIN/mvn|plexus-classworlds" >/dev/null 2>&1; then
      die "已经有一个 maven 在跑。这台机器同时跑两个 maven 会互相拖死（16G 超售），等它结束再双击。"
    fi
    export PATH="$MVN_BIN:$PATH"
    jar_before="$(stat -f %m "$JAR" 2>/dev/null || echo 0)"
    # 有源文件被删时必须 clean：不带 clean 的 package 只覆盖不删除，
    # 已删掉的 mapper XML 还留在 target/classes/mapper/ 里跟着进 jar，
    # 启动时 MyBatis 解析它、去找已删除的实体 → ClassNotFoundException 整个上下文起不来
    # （2026-10-07 删死模块实测：编译与 144 个单测全绿，jar 却起不来）
    mvn_args=(package -pl spzx-manager -am -DskipTests -q)
    [ -n "$deleted_src" ] && mvn_args=(clean "${mvn_args[@]}")
    say "  mvn ${mvn_args[*]}（约 1~2 分钟，日志 $RUN/package.log）"
    ( cd "$REPO" && mvn "${mvn_args[@]}" ) > "$RUN/package.log" 2>&1
    jar_after="$(stat -f %m "$JAR" 2>/dev/null || echo 0)"
    # 不看 mvn 的退出码：管道/插件告警会把它弄得不可信，只认 jar 是不是变新了
    [ "$jar_after" -gt "$jar_before" ] || die "打包后 jar 没变新，看 $RUN/package.log 最后 40 行：
$(tail -40 "$RUN/package.log")"
    say "  打包完成"
  else
    say "  jar 比所有源码都新 → 直接起，不重复打包"
  fi

  # 每个数字都有出处，别随手调（2026-10-06 实测）：
  #  -Xmx320m：jcmd 连量两次，堆"used" 282MB/156MB 里 186MB/59MB 是年轻代垃圾，**老年代存活恒 ~96MB**，
  #            320m 留 3.3 倍余量。不封顶时默认按物理内存 1/4 取（这台 16G = 4G 上限），那份跑一天 footprint 579MB。
  #  -Xss512k：默认线程栈 2048KB × 56 线程 = 112MB 预留 → 28MB。Spring/MyBatis 的栈深实测够用；
  #            万一报 StackOverflowError，第一项抬回 1m，别抬堆。
  #  Min/MaxHeapFreeRatio=20/40：SerialGC 才会把空余堆还回去，否则 committed 一直停在峰值。
  #  CICompilerCount=1 + TieredStopAtLevel=1：默认 4 个 JIT 线程，只到 C1 后 1 个就够，启动 CPU 直接少 3/4。
  #  MaxDirectMemorySize=64m：默认等于 Xmx（320m）的堆外配额，Tomcat NIO 用不到那么多。
  #  tomcat 16 线程 + commonPool 并行度 1：dev yml 写的是 50 线程，单人访问用不到；
  #            并行度压 1 的依据是 grep 全仓 0 处 parallelStream/ForkJoinPool/supplyAsync。
  #  不加 -Xrs：那会让 SIGTERM 跳过 shutdown hook，stop-local.sh 就优雅不掉它了。
  #  DevTools 不在 jar 里（spring-boot-maven-plugin 默认剔除，已 unzip 复核）→ `java -jar` 这条路天然没有
  #            那个每秒轮询 classpath 的重启器；现在 8501 那份空闲 CPU 主要就是它贡献的。
  say "  启动 java -jar spzx-manager.jar"
  bp="$(spawn "$BLOG" "$REPO/spzx-manager/target" \
      "$JAVA_BIN" \
      -Xms48m -Xmx320m -XX:MaxMetaspaceSize=256m -XX:ReservedCodeCacheSize=96m \
      -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -XX:CICompilerCount=1 -Xss512k \
      -XX:MinHeapFreeRatio=20 -XX:MaxHeapFreeRatio=40 -XX:MaxDirectMemorySize=64m \
      -XX:+ExitOnOutOfMemoryError \
      -Djava.awt.headless=true -Dfile.encoding=UTF-8 \
      -Djava.util.concurrent.ForkJoinPool.common.parallelism=1 \
      -Dserver.tomcat.threads.max=16 -Dserver.tomcat.threads.min-spare=2 \
      -jar "$JAR")"
  [ -n "$bp" ] || die "启动后端失败（python 没返回 pid）"
  echo "backend $bp" >> "$PIDS"
  say "  pid ${bp}，等端口（最多 180s，lazy-init 下第一次点页面还会更慢）"
  wait_port "$BPORT" 180 "$bp" || { tail -30 "$BLOG"; die "后端 180s 没起来，日志见 $BLOG"; }
  say "  ok :$BPORT 在听"
fi

say ""
say "=== [3/4] 前端 :$FPORT ==="
fp="$(listener "$FPORT")"
if [ -n "$fp" ]; then
  say "  已经有人在听（pid ${fp}）→ 复用，不动它"
else
  [ -d "$WEB/node_modules" ] || die "前端依赖没装：cd '$WEB' && npm ci（用 Node 23）"
  # shell 默认是 Node 14，vite 5 起不来且不会报错只会静默失败 —— 直接点 v23 的绝对路径，不 source nvm
  node_dir=""
  for c in "$HOME"/.nvm/versions/node/v23*/bin; do [ -x "$c/node" ] && node_dir="$c"; done
  [ -n "$node_dir" ] || die "找不到 Node 23（~/.nvm/versions/node/v23*/bin），先 nvm install 23"
  export PATH="$node_dir:$PATH"
  say "  启动 vite（node $("node" -v)，直连后端 ${BPORT}，不挂 mock）"
  # 384m 的依据：现在这份 vite 跑 3 天 19 小时，footprint 215MB、常驻 53MB，node 默认堆上限(~2G)根本用不到。
  # 只影响 dev server；`npm run build` 是另一条命令，不受这里限制。
  export NODE_OPTIONS=--max-old-space-size=384
  fp="$(spawn "$FLOG" "$WEB" node node_modules/vite/bin/vite.js)"
  [ -n "$fp" ] || die "启动前端失败（python 没返回 pid）"
  echo "frontend $fp" >> "$PIDS"
  wait_port "$FPORT" 60 "$fp" || { tail -20 "$FLOG"; die "前端 60s 没起来，日志见 $FLOG"; }
  say "  ok :$FPORT 在听"
fi

say ""
say "=== [4/4] 结果 ==="
while read -r who pid; do
  [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null || continue
  mb="$(footprint -p "$pid" 2>/dev/null | grep -o 'Footprint: [0-9]* MB' | awk '{print $2}')"
  tty="$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')"
  say "  本脚本起的 $who: pid ${pid}，footprint ${mb:-未知}MB，tty=${tty:-?}（?? = 已脱离控制终端，关窗口带不走它）"
done < "$PIDS"
say "  RSS 会低估好几倍，判占用只看 footprint（这台机器 swap 已用 $(sysctl -n vm.swapusage | awk '{print $6}')）"
say "  日志：backend $BLOG | frontend $FLOG"
say "  停止：再双击一次桌面的『运营后台开关』——只会停本脚本起的进程。"
open "http://localhost:$FPORT/" 2>/dev/null || true
