#!/bin/bash
# 中午静默窗口 (12:03-13:57) 专用 (2026-10-19)：静默拉起 9222 → 只读探针
# 静默 = 窗口模式(会话有效) + -32000 离屏 + CDP minimize 压回；探针 12:25 前收兵, 12:30 sync 共用此 Chrome
LOG=/tmp/noon_probe.log
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python

echo "[$(date '+%F %T')] === noon window start ===" >> "$LOG"
if ! curl -s -m 3 http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
  nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile \
    --no-first-run --disable-extensions \
    --disable-features=TranslateUI,site-per-process --disable-background-timers \
    --disable-backgrounding-occluded-windows --disable-background-networking \
    --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
    --window-position=-32000,-32000 --window-size=1400,900 \
    "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818" >> "$LOG" 2>&1 &
  for i in $(seq 1 30); do
    curl -s -m 2 http://127.0.0.1:9222/json/version >/dev/null 2>&1 && break
    sleep 2
  done
fi
sleep 3
"$PY" /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/cdp_minimize.py 9222 >> "$LOG" 2>&1 || true
echo "[$(date '+%F %T')] chrome silent up, running probes" >> "$LOG"
"$PY" "$DIR/probe_noon_recon.py" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] probes done ===" >> "$LOG"
