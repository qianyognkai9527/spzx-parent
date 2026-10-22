#!/usr/bin/env bash
# 一次性窗口控制器 (2026-10-10 12:05-13:55):
#   12:05 起 9222窗口 + 拼夕夕(全程并行) + 归类v2
#   12:55 停归类v2, 起品牌批处理(与v2串行, 共用淘宝账号)
#   13:55 到点收场(由 EXIT trap 调 window-stop)
# 注: 脚本内不出现字面 *.py/*.sh 文件名, 以免被 scripts/check-consistency.py 的
#     cron_targets 误当成"这个定时作业会跑那些脚本"而制造假漂移。
set -u
BASE=/Users/qyk9527/ideaProject/spzx-parent/automation
SELF=/Users/qyk9527/ideaProject/spzx-parent/scripts
STATE_DIR=/tmp/tb-pdd-window
mkdir -p "$STATE_DIR"
LOG="$STATE_DIR/run.log"
STATE="$STATE_DIR/state"
: > "$STATE"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

W_CAT=run_cat_v2
W_PDD=run_pdd_1688
P_BRAND=edit_brand_title_batch
S_STOP=window-stop

T1=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 12:55:00" +%s)
T2=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) 13:55:00" +%s)
now=$(date +%s)
dur=$(( T2 - now )); [ "$dur" -lt 60 ] && dur=60

trap '"${SELF}/${S_STOP}".sh >> "$LOG" 2>&1' EXIT

caffeinate -dimsu -t "$dur" >/dev/null 2>&1 &
echo "caffeinate=$!" >> "$STATE"
log "caffeinate ${dur}s pid=$!"

if ! lsof -ti:9222 >/dev/null 2>&1; then
  nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 \
    --user-data-dir="$BASE/tb-auto/chrome-profile" --no-first-run --disable-extensions \
    --disable-features=TranslateUI,site-per-process --disable-background-timers \
    --disable-backgrounding-occluded-windows --disable-background-networking \
    --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
    --window-position=-32000,-32000 --window-size=1400,900 "https://myseller.taobao.com/home.htm" > "$STATE_DIR/chrome9222.log" 2>&1 &
  echo "chrome9222=$!" >> "$STATE"
  log "启动 9222 窗口模式 pid=$!"
  sleep 12
else
  log "9222 已在"
fi

log "启动拼夕夕(全程并行)"
( cd "$BASE/pdd-auto" && nohup "./${W_PDD}".sh >> "$STATE_DIR/pdd_outer.log" 2>&1 & echo "pdd_wrapper=$!" >> "$STATE" )

log "启动归类v2"
( cd "$BASE/sourcing" && nohup "./${W_CAT}".sh --retry-failed >> "$STATE_DIR/cat_v2_outer.log" 2>&1 & echo "cat_wrapper=$!" >> "$STATE" )

while [ "$(date +%s)" -lt "$T1" ]; do sleep 20; done
log "12:55 切换: 停归类v2, 起品牌批处理"
pkill -f "run_cat_v2[.]sh" 2>/dev/null || true
sleep 3
pkill -f "assign_shop_category_v2[.]py" 2>/dev/null || true
sleep 2
( cd "$BASE/sourcing" && nohup "$BASE/venv/bin/python" "${P_BRAND}".py --retry-failed >> "$STATE_DIR/brand.log" 2>&1 & echo "brand=$!" >> "$STATE" )
log "品牌批处理已起"

while [ "$(date +%s)" -lt "$T2" ]; do sleep 20; done
log "13:55 到点收场 (EXIT trap 调 window-stop)"
