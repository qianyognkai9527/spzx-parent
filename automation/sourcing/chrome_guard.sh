#!/bin/bash
# chrome_guard.sh — A 方案共用守卫 (2026-10-19)：任务脚本 source 后调用 ensure_chrome
# 语义: Chrome 不在线 → 静默拉起(窗口模式离屏+minimize, 绝不可见) + 等 CDP 就绪;
#       在线但 0 标签(病态, connect 必报 context management) → 补守卫标签。
# 用完即走由 scheduled killer 负责(13:10；夜间链尾自收, 见 spec), 本脚本只管「起」。

ensure_chrome() {
  local PORT=9222
  local GUARD_URL="https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"
  if curl -s -m 3 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
    local n
    n=$(curl -s -m 3 "http://127.0.0.1:${PORT}/json/list" 2>/dev/null | grep -c '"type": "page"' || true)
    if [ "${n:-0}" -eq 0 ]; then
      curl -s -X PUT "http://127.0.0.1:${PORT}/json/new?https%3A%2F%2Fufuwu.1688.com%2Fpage%2Ffuwu_work_isv_container.htm%3Fappkey%3D2839818" >/dev/null 2>&1
      sleep 2
    fi
    return 0
  fi
  nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=${PORT} \
    --user-data-dir=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile \
    --no-first-run --disable-extensions \
    --disable-features=TranslateUI,site-per-process --disable-background-timers \
    --disable-backgrounding-occluded-windows --disable-background-networking \
    --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
    --window-position=-32000,-32000 --window-size=1400,900 \
    "${GUARD_URL}" >/dev/null 2>&1 &
  local i
  for i in $(seq 1 30); do
    curl -s -m 2 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1 && break
    sleep 2
  done
  curl -s -m 3 "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1 || return 1
  sleep 2
  /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python \
    /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/cdp_minimize.py ${PORT} >/dev/null 2>&1 || true
  return 0
}

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
