#!/usr/bin/env bash
# 幂等清场: 先停任务(wrapper+worker) -> 关 9222/9224 -> 复查 -> 卸载本次 LaunchAgent
# 可被窗口控制器(EXIT trap)和 13:55 安全网作业同时调用, 重复执行无副作用。
# 注: pkill/pgrep 的脚本名用 [.] 字符类, 避免被 check-consistency.py 的 cron_targets 误识别。
LOG=/tmp/tb-pdd-window/stop.log
STATE=/tmp/tb-pdd-window/state
mkdir -p /tmp/tb-pdd-window
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
log "== stop 开始 =="

# 1) 任务: 先 wrapper 后 worker
pkill -f "run_cat_v2[.]sh" 2>/dev/null && log "停 run_cat_v2 wrapper" || true
pkill -f "run_pdd_1688[.]sh" 2>/dev/null && log "停 run_pdd_1688 wrapper" || true
sleep 2
for pat in "assign_shop_category_v2[.]py" "edit_brand_title_batch[.]py" "create_pdd_product[.]py"; do
  pkill -f "$pat" 2>/dev/null && log "停 worker $pat" || true
done
sleep 2

# 2) caffeinate (优先按状态文件 pid, 兜底 pattern)
if [ -f "$STATE" ]; then
  cpid=$(awk -F= '$1=="caffeinate"{print $2}' "$STATE" | tail -1)
  [ -n "${cpid:-}" ] && kill "$cpid" 2>/dev/null && log "停 caffeinate $cpid" || true
fi
pkill -f "caffeinate -dimsu" 2>/dev/null || true

# 3) 浏览器(精准 pattern)
pkill -f "remote-debugging-port=9222" 2>/dev/null && log "关 9222" || true
pkill -f "remote-debugging-port=9224" 2>/dev/null && log "关 9224" || true
sleep 3

# 4) 复查
for p in 9222 9224; do
  if lsof -ti:"$p" >/dev/null 2>&1; then log "WARN 端口 $p 仍占用"; else log "端口 $p 已释放"; fi
done
rem=$(pgrep -fl "run_cat_v2[.]sh|run_pdd_1688[.]sh|assign_shop_category_v2[.]py|edit_brand_title_batch[.]py|create_pdd_product[.]py" 2>/dev/null)
[ -z "$rem" ] && log "无任务残留" || log "WARN 残留: $rem"

# 5) 卸载: start 先卸, stop 最后卸(可能中断本脚本, 故放最后)
label_start=com.spzx.tb-pdd-window-start
label_stop=com.spzx.tb-pdd-window-stop
launchctl bootout gui/$(id -u)/$label_start 2>/dev/null && log "bootout $label_start" || true
rm -f "$HOME/Library/LaunchAgents/$label_start.plist"
rm -f "$HOME/Library/LaunchAgents/$label_stop.plist"
launchctl bootout gui/$(id -u)/$label_stop 2>/dev/null && log "bootout $label_stop" || true
log "== stop 完成 =="
