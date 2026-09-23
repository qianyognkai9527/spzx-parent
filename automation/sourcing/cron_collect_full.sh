#!/bin/bash
# 每周六 03:00: 1688详情采集合并(SKU/库存/运费/销量补全, 为尺码同步攒数据)
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/cron_collect_full.log

curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || { echo "[$(date '+%m-%d %H:%M')] Chrome 9222 不在线, 跳过"; exit 0; }
pgrep -f assign_shop_category_v2 > /dev/null && { echo "[$(date '+%m-%d %H:%M')] 归类v2运行中, 跳过"; exit 0; }

echo "[$(date '+%m-%d %H:%M')] === collect_1688_full 开始 ===" >> $LOG
$PY collect_1688_full.py >> $LOG 2>&1
echo "[$(date '+%m-%d %H:%M')] === collect_1688_full 结束 ===" >> $LOG
