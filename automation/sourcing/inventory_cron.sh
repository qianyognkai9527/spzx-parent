#!/bin/bash
# 库存同步定时调度
# 用法: inventory_cron.sh [pool|full]  (默认 pool=优质池, full=全部商品)
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/inventory_cron.log
MODE=${1:-pool}

# 守卫: Chrome 9222 不在线 → 跳过
curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || { echo "[$(date '+%m-%d %H:%M')] Chrome 9222 不在线, 跳过"; exit 0; }
# 守卫: 归类v2运行中(同Chrome勿并行1688任务) → 跳过
pgrep -f assign_shop_category_v2 > /dev/null && { echo "[$(date '+%m-%d %H:%M')] 归类v2运行中, 跳过本轮"; exit 0; }

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存同步 $MODE 开始 ===" >> $LOG

# 1. 采集1688 SKU + 检测变化 (默认只扫优质池, full扫全部)
if [ "$MODE" = "full" ]; then
    $PY detect_stock_change.py >> $LOG 2>&1
else
    $PY detect_stock_change.py --pool >> $LOG 2>&1
fi

# 2. 检测提醒
$PY detect_alerts.py --type all >> $LOG 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存同步 $MODE 结束 ===" >> $LOG
