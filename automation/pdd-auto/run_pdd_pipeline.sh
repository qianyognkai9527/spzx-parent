#!/usr/bin/env bash
# PDD 边采边发管线: 每轮 [采集一批 -> 构建worklist -> 发布]; 发布遇风控(退出码42)则降级:
#   采集到底 + 跑「淘宝铺货失败任务」+ 冷却, 再继续. 全程可断点续跑.
cd "$(dirname "$0")"
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
SOURCING=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
CHUNK="${CHUNK:-30}"
COOLDOWN=1800
echo "===== [$(date '+%F %T')] 边采边发启动 CHUNK=$CHUNK ====="
while true; do
  before=$(wc -l < taobao_product_data.jsonl 2>/dev/null || echo 0)
  echo "----- [$(date '+%F %T')] 采集一批 (当前 $before) -----"
  $PY collect_qianniu.py --from-isv --limit "$CHUNK"
  after=$(wc -l < taobao_product_data.jsonl 2>/dev/null || echo 0)
  echo "----- [$(date '+%F %T')] 构建 worklist -----"
  $PY build_pdd_worklist.py
  echo "----- [$(date '+%F %T')] 发布 -----"
  $PY create_pdd_product.py
  code=$?
  if [ $code -eq 42 ]; then
    echo "===== [$(date '+%F %T')] PDD 风控! 降级: 先采集到底 + 跑淘宝铺货失败任务 + 冷却 ====="
    $PY collect_qianniu.py --from-isv
    echo "----- [$(date '+%F %T')] 淘宝铺货失败任务 -----"
    ( cd "$SOURCING" && bash run_isv_republish.sh ) || echo "[warn] 淘宝失败任务退出码 $?"
    echo "===== [$(date '+%F %T')] 冷却 $((COOLDOWN/60))m 后继续 ====="
    sleep $COOLDOWN
    COOLDOWN=$(( COOLDOWN * 2 )); [ $COOLDOWN -gt 7200 ] && COOLDOWN=7200
    continue
  fi
  echo "===== [$(date '+%F %T')] 轮次完成: 采集 $before -> $after ====="
  if [ "$before" = "$after" ]; then
    echo "===== [$(date '+%F %T')] 采集无新增, 管线结束 ====="
    break
  fi
  sleep 30
done
