#!/bin/bash
# isv_sku_match 全量自愈 wrapper：脚本异常退出(风控瞬断/CDP抖动)后冷却重试，断点续跑。
# 用法: nohup ./run_sku_match.sh > /tmp/sku_match_wrap.log 2>&1 &
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/sku_match_run.log
MAX_ROUNDS=40          # 每轮失败冷却 300s；40 轮足够覆盖整晚
CHROME_LOG=/tmp/chrome9222_window.log
cd "$DIR" || exit 1

# 窗口守卫: macOS 会把"完全离屏"的窗口钳回可视区(--window-position 失效, 实测踩过),
# launchd 里 osascript 又没有辅助功能权限 → 用 CDP Browser.setWindowBounds 最小化,
# 每 60s 巡检一次(用户手动还原也会被压回去)。守卫随 wrapper 存活, bootout 一并回收。
(
  while true; do
    sleep 60
    curl -s --max-time 3 http://127.0.0.1:9222/json/version > /dev/null 2>&1 || continue
    $PY /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/cdp_minimize.py 9222 >> "$LOG" 2>&1
  done
) &

ensure_chrome() {
  # 9222 无可用标签页(CDP 挂死/窗口被关/渲染进程崩) → 精准重启窗口模式(屏幕外, 防误关)
  if ! curl -s --max-time 5 http://127.0.0.1:9222/json/list 2>/dev/null | grep -q '"type": "page"'; then
    echo "[$(date '+%F %T')] Chrome 9222 无可用标签页, 自动重启" >> "$LOG"
    lsof -ti:9222 | xargs kill 2>/dev/null
    sleep 3
    rm -f /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile/Singleton* 2>/dev/null
    nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --remote-debugging-port=9222 \
      --user-data-dir=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile \
      --no-first-run --disable-extensions \
      --disable-features=TranslateUI,site-per-process --disable-background-timers \
      --disable-backgrounding-occluded-windows --disable-background-networking \
      --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
      --start-minimized --window-position=-32000,-32000 --window-size=1400,900 \
      "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818" >> "$CHROME_LOG" 2>&1 &
    sleep 10
    # 最小化窗口(--window-position=-32000 被 macOS 钳回可视区, 只能靠 CDP; launchd 里 osascript 无权限)
    $PY /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/cdp_minimize.py 9222 >> "$LOG" 2>&1
    curl -s --max-time 5 http://127.0.0.1:9222/json/list 2>/dev/null | grep -q '"type": "page"' \
      && echo "[$(date '+%F %T')] Chrome 重启 OK" >> "$LOG" \
      || echo "[$(date '+%F %T')] Chrome 重启后仍无标签页, 本轮放弃" >> "$LOG"
  fi
}

RC5=0
for i in $(seq 1 $MAX_ROUNDS); do
  # 防双跑：已有实例在跑就等它
  if pgrep -f "python.*isv_sku_match\.py" > /dev/null; then
    echo "[$(date '+%F %T')] 第$i轮: 已有实例在跑, 等 300s" >> "$LOG"
    sleep 300
    continue
  fi
  ensure_chrome
  echo "[$(date '+%F %T')] === 第 $i/$MAX_ROUNDS 轮开始 ===" >> "$LOG"
  $PY -u isv_sku_match.py --apply --gap 10 >> "$LOG" 2>&1
  rc=$?
  echo "[$(date '+%F %T')] === 第 $i 轮退出 rc=$rc ===" >> "$LOG"
  if [ "$rc" = "0" ]; then
    echo "[$(date '+%F %T')] 全量完成" >> "$LOG"
    exit 0
  fi
  # 连续 2 次 rc=5(翻页失效, 页面僵死但标签还在) → 杀 Chrome, 下轮 ensure_chrome 会重启
  if [ "$rc" = "5" ]; then
    RC5=$((RC5 + 1))
    if [ "$RC5" -ge 2 ]; then
      echo "[$(date '+%F %T')] 连续${RC5}次翻页失效, 强制重启 Chrome" >> "$LOG"
      lsof -ti:9222 | xargs kill 2>/dev/null
      sleep 3
    fi
  else
    RC5=0
  fi
  sleep 300
done
echo "[$(date '+%F %T')] 达到最大轮数 $MAX_ROUNDS, 停止" >> "$LOG"
exit 2
