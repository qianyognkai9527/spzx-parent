#!/usr/bin/env bash
# 1688 直铺批量发布(无人值守):
#  - 每轮前检查 9224, 掉线则自动重启 Chrome
#  - 每轮结束自动收尾: 抓在售/驳回 -> 登记进后台 -> 存量体检（2026-10-05 加，之前靠人手跑三步）
#  - 风控(退出码42) 冷却 30m→60m→120m 封顶后重试
#  - 验证码交给 create_pdd_product 处理：第 1 次等 300s 留人工救援，第 2 次直接隔离不再等
# 断点续跑: 按 pdd_create_progress_1688.json 跳过 done；合规闸门也在那边（连浏览器之前拦）。
# 收尾可能失败(比如 9224 掉了)，失败不影响发布主流程，只在日志里记一笔。
cd "$(dirname "$0")"
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=pdd_run_1688.log
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE=/Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/chrome-profile
COOLDOWN=1800

ensure_chrome() {
  curl -s --max-time 3 http://127.0.0.1:9224/json/version >/dev/null 2>&1 && return 0
  echo "[$(date '+%F %T')] 9224 掉线, 重启 Chrome" >> "$LOG"
  nohup arch -arm64 "$CHROME" --remote-debugging-port=9224 --user-data-dir="$PROFILE" \
    --no-first-run --disable-extensions --disable-features=TranslateUI,site-per-process \
    --disable-background-timer-throttling --disable-backgrounding-occluded-windows \
    --disable-background-networking --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
    --window-position=0,0 --window-size=1400,900 "https://mms.pinduoduo.com/" > chrome_9224_restart.log 2>&1 &
  sleep 8
}

# 铺完一批要做的三件事，顺序不能反：先抓店铺现状(在售+驳回)，再按它登记进后台，最后出体检报告。
post_round() {
  ensure_chrome || true
  echo "[$(date '+%F %T')] ---- 收尾: 抓店铺现状 ----" >> "$LOG"
  $PY sync_pdd_store.py >> "$LOG" 2>&1
  echo "[$(date '+%F %T')] ---- 收尾: 登记进后台 ----" >> "$LOG"
  $PY import_pdd_products.py >> "$LOG" 2>&1
  echo "[$(date '+%F %T')] ---- 收尾: 存量合规体检 ----" >> "$LOG"
  $PY audit_pdd_catalog.py >> "$LOG" 2>&1
  echo "[$(date '+%F %T')] ---- 收尾结束 ----" >> "$LOG"
}

# 只想跑一次收尾（比如铺完后补登记）: POST_ROUND_ONLY=1 bash run_pdd_1688.sh
if [ "${POST_ROUND_ONLY:-0}" = "1" ]; then
  post_round
  exit 0
fi

ROUND=0
while true; do
  ROUND=$(( ROUND + 1 ))
  ensure_chrome
  echo "===== [$(date '+%F %T')] 第 $ROUND 轮发布开始 =====" >> "$LOG"
  $PY create_pdd_product.py --source 1688 >> "$LOG" 2>&1
  code=$?
  echo "[$(date '+%F %T')] 第 $ROUND 轮 create_pdd_product 退出码=$code" >> "$LOG"

  # 不管这轮怎么结束都收尾一次：拦截/风控/正常结束，店铺现状都变了
  post_round

  if [ $code -eq 0 ]; then
    echo "[$(date '+%F %T')] 第 $ROUND 轮结束(可能仍有失败), wrapper 退出" >> "$LOG"
    break
  fi
  if [ $code -eq 42 ]; then
    echo "[$(date '+%F %T')] 风控, 冷却 $((COOLDOWN/60))m 后重试" >> "$LOG"
    sleep $COOLDOWN
    COOLDOWN=$(( COOLDOWN * 2 )); [ $COOLDOWN -gt 7200 ] && COOLDOWN=7200
  else
    echo "[$(date '+%F %T')] 异常退出($code), 5m 后重试" >> "$LOG"
    sleep 300
  fi
done
