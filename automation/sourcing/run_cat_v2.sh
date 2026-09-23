#!/bin/bash
# 合并版归类 v2 + 风控自愈循环: 撞风控(exit 42) → 阶梯冷却(20m→40m→2h 封顶) → 自动续跑; 期间顺手跑降级任务(货源销量计算)
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=${LOG:-/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/cat_v2_run.log}
MAX_RETRY=${MAX_RETRY:-20}

# 单实例锁: 防误起双实例(同 Chrome 并行 1688 任务=风控红线); shlock 自动回收死进程遗留的陈旧锁
LOCK=/tmp/cat_v2.lock
if ! shlock -p $$ -f "$LOCK"; then
    echo "[$(date '+%m-%d %H:%M:%S')] 已有实例在运行(锁 $LOCK), 本次不启动" >> $LOG
    exit 1
fi

ATTEMPT=0
while [ $ATTEMPT -lt $MAX_RETRY ]; do
    ATTEMPT=$((ATTEMPT+1))
    echo "[$(date '+%m-%d %H:%M:%S')] === v2 第 $ATTEMPT/$MAX_RETRY 轮启动 ===" >> $LOG
    $PY assign_shop_category_v2.py "$@" >> $LOG 2>&1
    CODE=$?
    echo "[$(date '+%m-%d %H:%M:%S')] v2 退出 code=$CODE" >> $LOG
    if [ $CODE -eq 42 ]; then
        # 阶梯冷却(2026-09-18 用户选定): 第1轮风控 20m, 第2轮 40m, 第3轮起 2h 封顶
        # (RGV587 有识别补丁后, 重试撞风控不烧商品, 每次试探仅 1-2 分钟)
        case $ATTEMPT in
            1) CD=1200; CDM=20m ;;
            2) CD=2400; CDM=40m ;;
            *) CD=7200; CDM=2h ;;
        esac
        echo "[$(date '+%m-%d %H:%M:%S')] 风控, 降级跑货源销量计算(秒完)后冷却 ${CDM}" >> $LOG
        $PY detect_stock_change.py --pool >> $LOG 2>&1
        echo "[$(date '+%m-%d %H:%M:%S')] 冷却 ${CDM} 后自动续跑..." >> $LOG
        sleep $CD
    else
        echo "[$(date '+%m-%d %H:%M:%S')] 非风控退出(完成或异常), 循环结束" >> $LOG
        break
    fi
done
echo "[$(date '+%m-%d %H:%M:%S')] === v2 自愈循环结束 (共 $ATTEMPT 轮) ===" >> $LOG
