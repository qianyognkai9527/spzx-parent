#!/usr/bin/env bash
# 启动 Chrome 9224 (PDD 铺货用) - 窗口模式(PDD 提交类不能用 headless), 离屏
arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9224 \
  --user-data-dir="/Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/chrome-profile" \
  --no-first-run \
  --disable-features=TranslateUI,site-per-process \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows \
  --window-position=-32000,-32000 --window-size=1400,900 \
  "https://mms.pinduoduo.com/"
