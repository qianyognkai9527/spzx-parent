#!/usr/bin/env bash
# 淘宝铺货批量启动脚本 (下班后手动跑)。
# 前置: Chrome 9222 已开 + 已登录1688 + 手动点开"铺货日志"页的"铺货失败"tab。
#   (Ant SPA 菜单脚本点不动, 必须手动开, 否则批量采不到数据)
set -e
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto

if ! curl -s http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
  echo "✗ Chrome 9222 未开。先启动:"
  echo '  ./run_chrome.sh'
  exit 1
fi
echo "✓ Chrome 9222 已开"
echo "⚠️  请确认已在浏览器里手动点开 铺货日志 -> 铺货失败 tab (脚本无法点 Ant SPA 菜单)"
echo "按回车继续启动批量, Ctrl+C 取消..."
read -r

# 可选: --test (只处理已打开的编辑页不提交) / --limit N
nohup venv/bin/python3 auto_list.py > batch.log 2>&1 &
echo "✓ 批量已启动 (PID $!), 日志: batch.log"
echo "  tail -f /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/batch.log"
