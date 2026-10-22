# AGENTS.md — automation/（Python 电商自动化跨目录经验）

跨 `sourcing/`/`tb-auto/`/`pdd-auto/`/`fanqie-publish/` 的通用经验与快速命令。逐目录坑位见各自 `AGENTS.md`；**Chrome 红线 / CDP 端口分工见全局 `~/.config/opencode/AGENTS.md`**；cron/定时任务见 `~/docs/cron.md`；小说发布见 `~/docs/novel-writing.md`。

## 高价值经验

- **抖店直建** `sourcing/create_douyin_product.py`：不连 9223，自启有窗口 Chrome（登录态 `/tmp/chrome-douyin-create`，重启即清要扫码）。进度 `douyin_create_progress.json` 只跳过 `saved`；续跑 `--batch 99999`+bash 循环，**每次开新日志再 grep**（复用旧日志误判完成）。`saved`=发布成功但下架（在售走 `sourcing/_archive_20260906/batch_relist.py`）；10001010A 仅警告；顽固失败会空转（日志「完成」但 saved 不涨）→ 收尾看 progress 分布。表单坑位见 sourcing/AGENTS.md。
- **详情图重采**：`scrape_1688_for_douyin.py --redetail`（进度 `redetail_douyin_progress.json`、日志 `redetail_run.log`）。
- **淘宝归类 v2** `assign_shop_category_v2.py`+`run_cat_v2.sh`：单次编辑=归类+调价+尺码台账，进度 `shop_cat_v2_progress.json`。**调价=货源价+130（最低SKU≈159）只限「家居服/睡衣」「美甲」**（其他类目勿动价）；旧价=×3 或 ×3.9。exit 42→降级 `detect_stock_change.py --pool`；提交前自动删横版视频。开跑前 `collect_in_stock_current.py`（`--list sold_out` 采在售池带 tab 计数页数上限）→`build_shop_cat_plan.py --merge`（旧判定保留+pool 字段）。续跑 `--retry-failed`；定向 `--ids id1,id2`（可补跑 skipped，done 仍跳过）。2026-09-24 起支持**在售商品**（上架状态原样维持；探路验收过）。onsale 美甲 754：脏色已可程序清洗（09-26，「编辑规格」清【甲型】+先填款式再重建，见 sourcing/AGENTS.md），最终卡点=换主图（PIC_STEAL）。**RGV587**：headless 必拦（仅「我知道了」弹窗）→ 提交类必须窗口模式；已自愈（冷却阶梯 20m→40m→2h 封顶），连续多轮才需人工滑块（须无任务时正常窗口重启 9222）。扩大覆盖版已跑（`spzx-parent/docs/superpowers/{specs,plans}/2026-09-24-shop-cat-v2-onsale*`）。
- **杀长任务**：抖音直建杀 bash 包装+python 两个（只杀 python 会被重启）；归类 v2 冷却期只杀 `run_cat_v2.sh` 包装。杀完 pgrep 复查。
- CDP 统一 `sourcing/cdp_utils.py` 的 `connect_cdp(port, keep_urls, log)`+结尾 `page.close()`；禁裸 `connect_over_cdp`；0 标签坏下次 connect → 退出前 /json/new 补守卫 tab。Chrome 必须 `arch -arm64`；窗口模式勿 `--disable-gpu`。
- 同一 Chrome 勿并行两个 1688 CDP 任务（风控账号级，跨实例也触发）。
- SPA 同 URL 改 query 不重渲染→新开 page 或点按钮翻页；React 受控输入 `fill()`+`press('Tab')`；SVG 无 `.click()` 用 dispatchEvent；提交结果看网络响应/弹框关闭，页面文本不可靠。
- 1688 关键词 GBK 编码（`quote(kw.encode('gbk'))`）；请求过密冷却 20-25min，风控期停跑。
- sycm 必须窗口模式（headless 必被 RGV587 拦）；`sycm_item_snapshot.py`+`hot_rank.py`（`--date-type recent7`，srcId 用 source_product_code）。
- 淘宝巡检弹窗遮列表先点「忽略」；翻页点「下一页」；标题基线 jsonl 会过期，以实地搜索为准。
- **新增截图/快照落盘点必须登记** `scripts/cleanup_runtime.sh` 的模式白名单（spec schedule-optimization §9），否则视为 bug——磁盘只增不删的教训：auto_list 时间戳截图曾无限累积。

## 快速命令

```bash
tb-auto/run_chrome.sh        # 9222 headless（仅浏览/采集类）
sourcing/run_chrome.sh       # 9223 headless
# 9222 窗口模式（淘宝提交类必用如归类 v2；勿带 --headless/--disable-gpu）：
# nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 \
#   --user-data-dir=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile --no-first-run --disable-extensions \
#   --disable-features=TranslateUI,site-per-process --disable-background-timers \
#   --disable-backgrounding-occluded-windows --disable-background-networking \
#   --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
#   --window-position=-32000,-32000 --window-size=1400,900 "https://myseller.taobao.com/home.htm" &
open -na "Google Chrome"     # 启完自动化 Chrome 后恢复日常浏览器
# 铺货: tb-auto/ 下 ./run_batch.sh
# 选品: sourcing/ 下 nohup /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python source_1688.py > source_run.log 2>&1 &
# 落库: /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python import_to_db.py（sourcing/ 下）
# 后端: mvn install -pl spzx-model -DskipTests -q → spring-boot:run -pl spzx-manager
```
