#!/usr/bin/env bash
# 只采集+构建(发布暂停): 把 isv_offer_taobao_map 里剩余商品的千牛数据采完, 并构建好 worklist(下图/缩图/过滤).
# 配额恢复后, 直接跑 create_pdd_product.py 即可集中发布.
cd "$(dirname "$0")"
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
echo "===== [$(date '+%F %T')] 只采集管线启动 ====="
for i in $(seq 1 40); do
  before=$(wc -l < taobao_product_data.jsonl 2>/dev/null || echo 0)
  $PY collect_qianniu.py --from-isv --limit 50
  after=$(wc -l < taobao_product_data.jsonl 2>/dev/null || echo 0)
  echo "----- [$(date '+%F %T')] 轮 $i: 采集 $before -> $after -----"
  [ "$before" = "$after" ] && break
  sleep 10
done
echo "----- [$(date '+%F %T')] 构建 worklist -----"
$PY build_pdd_worklist.py
echo "===== [$(date '+%F %T')] 只采集管线结束(可跑 create_pdd_product.py 发布) ====="
