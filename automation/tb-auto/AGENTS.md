# AGENTS.md

Browser automation (Python 3.9 venv + Playwright async API) that re-lists failed 1688→Taobao product drafts: sets price ×3, selects store category 家居服/睡衣, sets 上架时间=放入仓库, enables 商品预检, generates a compliant 款号, and submits to warehouse. Progress persists across runs for breakpoint resume. NOT a git repo - don't run git commands here.

## Environment / Chrome (critical)

- Chrome must already be running with CDP before any script runs:
  ```bash
  arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile" \
    --no-first-run "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"
  ```
- Chrome 150+ refuses `--remote-debugging-port` with the default profile — you MUST use a non-default `--user-data-dir` (the `chrome-profile` dir holds the 1688 login).
- Use `arch -arm64` prefix: the default shell runs under Rosetta (x86) and launching Chrome without it is extremely slow.
- Do NOT close/reopen the browser during a run; it raises risk-control flags.

## Run commands

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
nohup venv/bin/python3 auto_list.py > batch.log 2>&1 &   # full batch (resumes from progress.json)
venv/bin/python3 auto_list.py --test                     # process an already-open edit page, no submit
venv/bin/python3 auto_list.py --limit N                  # process at most N products
```

Flags are parsed from `sys.argv` in `auto_list.py`'s `__main__` (no argparse) - add new flags there.

## Prerequisites before running

- User must MANUALLY click "铺货日志" in the 1688 sidebar and select the 铺货失败 tab first. The Ant Design SPA menu CANNOT be navigated by script clicks — the batch only works if the 铺货日志 page is already open. (Deletion scripts `delete_adult*.py` navigate pages themselves.)
- Content lives in the iframe whose URL contains `isv-container` (Ant Design). Taobao edit page is `item.upload.taobao.com` (Next UI; fields use `sell-field-*` / `struct-*` IDs).

## Behavior / gotchas

- **款号 rule** (`rules.py:generate_style_number`): 2 uppercase letters + 3 digits; first digit must NOT be 4; no "38" substring.
- **Operation order**: 价格×3 -> 店铺中分类=家居服/睡衣 -> 上架时间=放入仓库 -> 商品预检. The 商品预检 checkbox is only enabled AFTER 放入仓库 is selected (code marks this 关键).
- **Two-tier submit**: first `do_submit` runs with the minimal ops above. If it fails for ANY reason (not a specific error message), `fill_category_attributes` fills empty required category attributes from a title-aware `attr_rules` dict, then resubmits.
- **Slider (阿里云滑块)**: triggered by rapid operations / attribute filling. Detection is size-aware (`#nc_1_wrapper` etc., >150×30). 三种行为: (a) 编辑页处理中触发 → 该商品标记 failed 继续; (b) **ISV 铺货日志页触发 → 保存 progress 并整个退出 batch**（不会继续）; (c) 提交后 verify_submission 触发 → **最多等 10 分钟人工过验证**再重试提交。运行中需要人去 9222 Chrome 手动拖滑块。
- **Shop-restriction permanent skip**: 情趣内衣/成人-category products ALWAYS fail with "成人类目市场为专营制" (store lacks adult-market qualification). These are added to `processed` so they are never retried — do not treat as retryable.
- **Progress** (`progress.json`): `processed` (list of row_keys, includes permanently-skipped) + `failed` (list, retried next run) + `count` (= len(processed)). `session_failed` is an in-memory set that resets each run - it only prevents same-run infinite retry and is NOT persisted. Do not lose this file — it is the only resume state.
- **价格×3** (`auto_list.py` ~L183): 一口价 and SKU prices ×3. `base_price` defaults to `1.01` when the original 一口价 is ≤0 or unparseable. SKU inputs whose value has no decimal point are skipped (they're stock counts, not prices); 0-price SKUs get the ×3 `base_price`, not left at 0.
- **Timing / batch breaks** (`config.py`): 8-15s between products (`MIN_DELAY=8, MAX_DELAY=15`). Every 80 products pauses 2-3 min (`BATCH_50=80`, break 120-180s); every 400 products pauses 10-15 min (`BATCH_200=400`, break 600-900s). A full batch runs for hours - a long pause is expected, not a hang.
- **"处理完成"≠全部清完**: batch 边处理边删铺货日志条目导致分页错位、会漏采; 日志写"已到第一页,没有更多页面了"时可能仍剩几百条在铺货失败列表。重跑前/后必须用 CDP 读 ISV 铺货失败 tab 的 `共 N 条` 和 `progress.json` 对账, 数值不降就继续跑。

## Maintenance scripts (all in repo)

- `delete_adult3.py` — delete remaining 情趣内衣 products from the failed list (ADULT_KEYWORDS: 情趣, 圣诞装, 制服, 角色扮演, 兔女郎, 丁字裤, 开裆, 免脱, 三点, 女仆, 连体衣, 绳衣). Set list to 100条/页 first via `.ant-pagination-options-size-changer` for speed.
- `scan_adult.py` — scan all pages, count remaining adult products (run to verify deletion is complete).
- `rules.py:infer_attributes` is imported by `auto_list.py` but NEVER called - dead code; real attribute inference lives inline in `fill_category_attributes`.
- Many `inspect_*` / `diagnose_*` / `test_*` scripts are one-off debugging tools; `auto_list.py`, `rules.py`, `config.py` are the real code.

## 阿里妈妈关键词出价批量修正（`adjust_alimama_bid.py`，可反复跑）

**用途**：万相台「关键词推广标准计划」下**所有单元**的关键词出价，按「流量解析→竞争流量透视→核心流量来源=手淘的市场均价」批量改写。
**为什么要反复跑**：市场均价随**行情/季节**变（如秋冬外套 vs 夏季），且**人群溢价一旦调整，出价必须同步重算**——出价是溢价的函数，不是独立常量。这是一条常态化流程，不是一次性任务。

**公式（与 `KwBidCalculator` 同口径）**：
```
关键词出价(基础出价) = 手淘市场均价 / ((1 + 人群溢价%) × 分时折扣%)
```
- 默认 `溢价=300%、折扣=35%` → 除以 `1.4`；**全能调价未开不计**。
- 向下取到分（`money_floor2`，先修浮点毛刺再 FLOOR）；低于 `--min-bid`（默认 0.05）抬到 min-bid。
- 查不到「手淘」行 / 无市场均价 → 记 `skip_no_market` 跳过，不猜。

**前置条件**：
- 9222 自动化 Chrome 以**窗口模式**开着（headless 会话易过期 / RGV587），已登录万相台；`adjust_alimama_bid.py` 只连 9222。
- 全程只用 **2 个标签**：1 个搜索详情页 + 1 个流量解析页，复用（脚本会自动关闭多余标签）。

**跑法**：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
# 只读预演（打印算出的价，不写）
venv/bin/python3 adjust_alimama_bid.py --campaign-id 83392643008 --dry-run --limit 5
# 真正写入（断点续跑：默认读 --report，已 ok 的词跳过）
venv/bin/python3 adjust_alimama_bid.py --campaign-id 83392643008 --apply --gap 1
# 行情/季节变了 或 改了人群溢价 → 按新参数整轮重算（忽略历史 ok）
venv/bin/python3 adjust_alimama_bid.py --campaign-id 83392643008 --apply --force --premium 250 --discount 35
# 只跑指定单元
venv/bin/python3 adjust_alimama_bid.py --campaign-id ... --adgroup-id 83440680802,83975300870 --apply
```
参数：`--campaign-id/--adgroup-id/--premium(默认300)/--discount(默认35)/--source(默认手淘)/--min-bid(0.05)/--gap(默认5，实测可降到1≈4-5s/词)/--limit/--report/--force/--dry-run|--apply`。不给 `--apply` 即 dry-run。

**页面/接口要点（已实测）**：
- 单元枚举：`one.alimama.com/adgroup/horizontal/findPage.json`（`pageSize` 分页，实测该计划 `count=70`；脚本重放 `pageSize=200` 一次拿全含暂停单元）。
- 搜索详情页关键词行：`a[href*="traffic-analysis"]`（href 里带 `bidwordId`，`word` 双重 URL 编码）；出价单元格 `#bidword_<id>_price`；修改图标 `i[mx-click*="editPrice"]`；回读单元格 `#bidword_<id>_bid_price`。
- 出价弹框：先选「手动出价」radio `input[name="price"][value="-1"]`（未选前 `input[mxc*="customPrice"]` 是 `disabled`）→ 填值 → 点含「手动出价+确定+取消」最小容器里的「确定」→ **回读校验** `readback=<值>元`。
- 流量解析页是 **hash 路由**：`.../index.html#!/insight/search/traffic-analysis/index?word=<双编码>&campaignId=&adgroupId=&bidwordId=`；表列＝展现指数/点击指数/点击率/点击转化率/**市场均价**/竞争指数，例 `手淘 205 11 4.80% 4.16% ￥0.63 181`。
- ⚠️ **同 URL 只换 hash 的 `goto` 属同文档导航，会读到上一个词的表**（曾误读立领外套）。脚本已改为**先 `about:blank` 再 goto** 强制整页重载，别改回去。

**报告 / 续跑**（`adjust_bid_report.json`，gitignore，是唯一断点状态）：
- `items[]` 每项 `{bidwordId,word,adgroupId,market,newBid,status,note}`；`status` ∈ `ok/skip_no_market/fail/dry`。
- 默认续跑跳过 `status=ok`；`record()` 按 `bidwordId` **就地更新**（复跑不堆重复行）。
- 风控熔断：连续 **8** 次取不到市场均价 → 退出码 4 停本轮；写入异常（`no_dialog`/`confirm:no btn`）→ 退出码 3 停并保留现场待查。

## 阿里妈妈关键词批量新增（`add_alimama_keywords.py`，可反复跑）

**用途**：给万相台「关键词推广」计划（本脚本按**智能计划**场景写，如「6脉之F自定义智能最大化收割」`campaignId=83949710619`，71 单元）的**每个单元批量新增关键词**。两来源各跑一次：①「AI选词」=`kr_fill_by_item`；②「关键词推荐→趋势机会词」=`kr_new_mta`。本类计划走系统智能出价，**不加出价**（`bidPrice:1,matchScope:4` 与页面 UI 一致）。

**选词（确定性规则，逐词可解释，见脚本 `GARMENT_FAMILIES/COLLARS/LENGTHS`）**：
- 词必须落在单元标题所属「品类家族」（sleep/coat/sweater/dress/skirt/pants/suit），且不得落别的家族（标题=皮草外套 → 可留「毛领大衣」「派克服」；剔「皮草背心马甲」「女开衫」「毛衣」）。
- **家族表 2026-10-17 扩展**（用户要上 牛仔裤/牛仔外套/半身裙/睡衣家居服）：新增 `sleep`(睡衣/睡裙/睡袍/家居服/家居裤)；`skirt` 从 dress 拆出（dress 只剩连衣裙——半身裙单元不再混进连衣裙词）；牛仔裤→pants、牛仔外套→coat 天然落对。**词家族判定=最长名词优先**（`word_family`：睡裙→sleep 不归 skirt、家居服套装→sleep、连衣裙→dress），平手按 `FAMILY_PRIORITY` 专精优先；`title_family` 无命中默认 coat 的坑仍在（新家族覆盖后睡衣/裙类标题都能命中，配饰类仍会默认 coat——加新品类时记得扩表）。
- **虚词剔除掩码材质**（2026-10-17 修）：BAD_CHARS 的「呢」曾误杀 毛呢外套/呢子大衣（MATERIALS 自己都有毛呢）——先掩 MATERIALS+呢子 再查虚词。
- **季节薄厚维度**（2026-10-17 用户要求，双向对称）：`season_side(标题)` 判边 warm/thin/None——暖边=秋冬/加绒/加厚/保暖/裸「绒」子串(珊瑚绒法兰绒金貂绒海岛绒摇粒绒…)/毛毛/貂/羊羔毛，薄边=夏季/薄款/轻薄/冰丝/雪纺/清凉/透气/短袖/无袖；**特异性优先 暖>薄>中性**（「加绒加厚…四季通用」判暖，「四季/无信号」判中性不设限）；暖标题剔薄边词、薄标题剔暖边词，判定在 `is_relevant` 内部用传入的 title 做，调用方零改动。薄款牛仔短裤拒「加绒牛仔短裤」、暖睡衣拒「冰丝睡裙」都有单测锁住。
- 排除词 `EXCLUDE_SUBSTR`（裤袜/袜裤）；领型维度加了 `吊带`；MATERIALS 加了 牛仔/珊瑚绒/法兰绒/金貂绒/海岛绒/丝绒。
- 规则单测：`./venv/bin/python tb-auto/test_alimama_word_rules.py`（跨家族互斥/最长名词/牛仔归位/裤袜排除/材质开关）。
- 领型/长度维度：标题声明的领型（如「立领」）命中同维度**不同值**即剔（圆领/翻领/连帽…）；长度同理。材质维度默认关，`--material-filter` 打开。
- 剔含 `的/了/吗/呢/吧` 的怪词、`len<2`；`搜索指数 >= --min-index`（默认 1000）；排序 `searchIndex desc`（并列次键 `marketClickRate`→`marketClickConversionRate`）；取前 `--top`（默认 50）；对单元已有词与两来源间去重（`norm`=去空白）。
- **兜底**：某来源按 `--min-index` 一个都没选中时，自动用 `--min-index-fallback`（默认 200）在该来源候选里再选一次，避免弱词单元被清空。

**删旧词（`--delete-old`）**：净结果=只保留本次新选词。**顺序是「先选→先加新词成功→再删旧词」，且只删与新选不重合的旧词**；若两来源合计 0 入选或加词全失败，则**保留旧词不删**（绝不把单元清空）。⚠️ 这条是 2026-10-12 用真金白银换来的：初版「先删后加」把 5 个单元删空（旧词删光、新词 0 入选）。**删除响应里的 `data.count` 不可信**（删 69 个也回 `count=2`）——判定以页面真值 `关键词（N）`/`tr.keyword-item[data-keyword-id]` 为准。

**页面 / 接口要点（实测）**：
- 单元枚举：重放 `one.alimama.com/adgroup/horizontal/findPage.json`（`pageSize=200`）拿全 71 单元（计划概览页表格只渲染当前分页，直接读 DOM 会漏）。`adgroupName`=商品标题。
- 单元详情页 URL 的 `tab=` **必须为空**（此页才有「关键词（N）」表 + 「添加关键词」入口）：`.../manage/search-detail?...&campaignId=<cid>&tab=&startTime=<d>&endTime=<d>&adgroupId=<aid>`。
- 加词按钮 `span[mx-click*="addBidword"]`；抽屉顶层 tab `a[mx-click*="magix-portsB"]`（文本 `流量智选|关键词组合|关键词推荐|AI选词`）；关键词推荐子项文本 `综合推荐词|店铺专有词|类目精准词|行业热门词|趋势机会词`。
- 候选词接口 `POST /bidword/suggest/kr/list.json`，`type`：AI选词=`kr_fill_by_item`、趋势机会词=`kr_new_mta`（另有 `kr_new_overall/kr_new_flow/kr_new_category/kr_new_industry`）。响应 `data.list[]` 含 `word/searchIndex/marketClickRate/marketClickConversionRate/competitionIndex/trendIndex/qscore/recReason`。
- 写入 `POST /bidword/add.json`；删除 `POST /bidword/delete.json`（每批 50）。两者都需 `csrfId`（会话内稳定）+ `loginPointId`（每次会话变），脚本从页面请求里现取；缺 csrfId 直连报 `2102001 bizLogin csrf检查未通过`。
- 单元现有关键词行：`tr.keyword-item[data-keyword-id]`，词文本在 `a[href*="traffic-analysis"]`（`data-keyword-id`=bidwordId）。**勾选抽屉行必须真实鼠标点击**（合成 `.click()` 不更新 magix state），但本脚本走直连 add.json，无需点复选框。

**跑法**：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation
# 只读预演
./venv/bin/python tb-auto/add_alimama_keywords.py --campaign-id 83949710619 --delete-old --dry-run --limit-units 2
# 真正写入（断点续跑：默认读 --report，单元+来源已 ok 的跳过）
./venv/bin/python tb-auto/add_alimama_keywords.py --campaign-id 83949710619 --delete-old --apply --gap 2
# 整轮重算（忽略历史 ok）
./venv/bin/python tb-auto/add_alimama_keywords.py --campaign-id 83949710619 --delete-old --apply --force
```
参数：`--campaign-id/--adgroup-id/--min-index(1000)/--min-index-fallback(200)/--top(50)/--gap(默认4)/--limit-units/--material-filter/--delete-old/--report/--force/--dry-run|--apply`。

**报告 / 续跑**（`add_keywords_report.json`，gitignore，唯一断点状态）：`items[]` 每项 `{adgroupId,title,method,words,picked,dropped,existing,deleted,status,note}`，`method` ∈ `ai/mta`，`status` ∈ `ok/fail/dry`；`_record()` 按 `(adgroupId,method)` 就地更新。**要重跑某单元先把它在 items 里的记录删掉**（否则 `status=ok` 会跳过）。

**已知坑**：
- **长跑后 `Page.evaluate: Target crashed`**（渲染进程崩，非整机 Chrome 挂；log 里 `Target crashed`）：脚本会退出，Chrome 随即触发 CDP 挂死（`connect_over_cdp` 连不上、HTTP `/json` 仍通）。恢复=精准 `kill` 该 PID（9222）+ 清 `chrome-profile/Singleton*` + **窗口模式**重启 9222，再续跑。
- 候选条数**非确定**：同一单元两次运行 AI选词候选可能 8 或 55、趋势机会词可能全 <1000 或大量 ≥1000（推测与抽屉缓存/单元当时关键词状态有关）。**先删后加会让候选变差**——这正是改成「先加后删」的原因之一。
- 与 `adjust_alimama_bid.py` 一样只连 9222；跑前确保 9222 窗口模式 Chrome 已登录万相台。

## 标准计划「重新选词 + 按公式算出价」（`pick_plan_keywords.py`，2026-10-14）

**用途**：标准计划建错要重建。新计划的商品(单元)/分时折扣由用户在页面选好；关键词**不照搬旧计划**，而是**重新选**——复用 `add_alimama_keywords.py` 的推荐候选+标题约束选词规则，选出后对每词查「手淘市场均价」、按公式算出基础出价，以**广泛匹配**写入新计划对应单元。

**公式**（与 `adjust_alimama_bid.py`/`KwBidCalculator` 同口径）：`出价 = 手淘市场均价 / ((1+溢价%) × 折扣%)`，默认溢价 300/折扣 35（÷1.4）；`money_floor2` 向下取到分、低于 min-bid(0.05) 抬高；查不到均价记 `skip_no_market` 跳过不猜。

**选词**：完全复用 `add_alimama_keywords.py`（`kr_fill_by_item` AI选词 + `kr_new_mta` 趋势机会词；搜索指数≥1000/兜底200、品类家族约束、领型长度冲突、虚词剔除、Top N、去重）。**词是平台推荐的，标题只作过滤约束**（不是从标题生成词）。匹配方式全部广泛=`matchScope:4`（页面默认）。

**复用而非重写**：`import add_alimama_keywords`（`get_units`/`goto_unit`/`open_drawer`/`click_tab`/`click_sub`/`existing_words`/`accepted_terms`/`_pick_with_fallback`/`_wait_type`/词典）与 `import adjust_alimama_bid`（`market_avg`/`TRAFFIC`/`calc_bid`/`money_floor2`）。**不改那两个脚本的行为**。

**跑法**（默认 dry-run，只有 `--apply` 才写）：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation
# 只读预演（先用旧/已知计划验证链路，不写）
./venv/bin/python tb-auto/pick_plan_keywords.py --campaign-id <新id> --limit-units 2 --top 30 --dry-run
# 真正写入
./venv/bin/python tb-auto/pick_plan_keywords.py --campaign-id <新id> --apply --top 30
```
参数：`--campaign-id(必填)/--adgroup-id/--premium(300)/--discount(35)/--source(手淘)/--min-bid(0.05)/--min-index(1000)/--min-index-fallback(200)/--top(30)/--match-scope(4=广泛)/--gap(2)/--limit-units/--material-filter/--report/--dry-run|--apply`。

**报告/续跑**（`pick_keywords_report.json`，gitignore）：`items[]` 每项 `{adgroupId,title,word,market,bid,matchScope,status,ts}`，`status ∈ dry/ok/skip_no_market/fail/skip_unit`；按 `(adgroupId,word)` 就地更新。**重跑天然幂等**：已写入的词会出现在单元页被去重跳过。

**已实测**：
- 关键词锚点 href 是 `#!/insight/search/traffic-analysis/index?word=<双重URL编码>&campaignId=..&adgroupId=..&bidwordId=..`，词是**双重 URL 编码**（`女皮草`→`%25E5%25A5%25B3...`）；**仅用词**拼该 URL 即可查均价（不依赖 bidwordId），无需先加词。
- 均价逐词查约 5-8s，脚本内**按词缓存**（同词跨单元不重复查）；`--top 30`×2 来源去重后每单元几十词，多单元为小时级长跑。
- 连续 8 次取不到均价 → 退出码 4 停本轮；写入异常 → 退出码 3 停并保留报告。
- 单测：`./venv/bin/python tb-auto/test_pick_plan_keywords.py`（双编码/URL 拼接/报告 upsert/品牌词过滤，无网络）。

**品牌词过滤（2026-10-17）**：`BRAND_TOKENS` 黑名单（琳琳/cc/鸭鸭/波司登…）+ ≥2 连续英文字母规则，命中即剔（`琳琳皮草`/`cc皮草`/`羽绒服鸭鸭` 实测混入过）；`--brand-blocklist` 可追加。**候选平台侧非确定 → 重跑会补词**（「重跑幂等」只对候选重合部分成立，2026-10-17 实测单元 41→70 词）——改价用 `reprice_plan.py`，**不要靠重跑 pick 改价**。

## 标准计划「重算出价 + 剔品牌词存量」（`reprice_plan.py`，2026-10-17）

**用途**：已写入的计划要整轮重算出价（均价读取路修过/溢价折扣变了/行情变了），或清品牌词存量。**不改词，只改价/删词**——补新词用 `pick_plan_keywords.py`。

**改价通道**：直连 `POST /bidword/update.json`（弹框路抓的包；`bidPrice` 是**字符串**，无需 suggestTraceId，批量 `bidwordList` 响应 `data.count` 校验，不足回落逐词）。⚠️ **`/bidword/add.json` 只新增不更新**——对已有词返回 ok 但出价不动（实测 0.66 写入回读仍 0.18）。⚠️ 平台传播有数秒延迟：**校验必须整页重载单元页再读**，同页立刻回读是旧值。

**删除通道**：品牌词走 `akw.delete_ids`（按 bidwordId 精准删，每批 50），删后 6s 重载单元页复核剩余=0。

**跑法**：
```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation
./venv/bin/python tb-auto/reprice_plan.py --campaign-id 84290744044 --premium 500 --dry-run --limit-units 2
./venv/bin/python tb-auto/reprice_plan.py --campaign-id 84290744044 --premium 500 --apply
```
参数：`--campaign-id(必填)/--adgroup-id/--premium(300)/--discount(35)/--source(手淘)/--min-bid(0.05)/--gap(2)/--limit-units/--brand-blocklist/--no-verify/--report/--dry-run|--apply`。现价已正确的词自动跳过（`same`），报告 `reprice_report.json` 按 bidwordId 就地更新、`meta.market` 按词缓存均价（断点续跑不重查）、`meta.empty_units` 列出零词单元。

**2026-10-17 实测**（计划 84290744044，溢价 500/折扣 35）：67 单元 463 独立词，same=2318 / **ok=210**（竞态错价全改）/ fail=0；删品牌词 4 个（琳琳皮草×2、cc皮草、羽绒服鸭鸭）复核 0 剩余；抽样 8 单元重载核对全对。

## 市场均价读取（`adjust_alimama_bid.market_avg`，2026-10-17 重写，两脚本共用）

**新流程**：页内换词（`placeholder=请输入关键词` 的输入框，React 原生 setter 填值）→ 点「查询」按钮 → 等**请求体含该词**的 `triggerDynamicModule.json` moduleId=1468（过去7天日均）响应 → 从响应体递归找 `pvName=手淘` 的 `avgPrice`（round 到分）。**响应与请求一一对应，无竞态**。找不到搜索框（首次加载）才回退老路 about:blank→goto 整页重载 + DOM 读表。

**为什么必须改**：① 反复整页刷新流量解析**易触发滑块**（2026-10-17 用户实测，页内换词后全程零整页刷新）；② 旧页内路读 DOM 表格有**渲染竞态**——表格更新慢于接口，轮询一看到「有数据」就返回，读到**上一个词**的均价（实测 `小香风外套` 记 2.85 真值 0.38）。流量解析页接口字段：moduleId 1571=词→类目列表、1465=概览、1468=竞争流量透视数据（`pvName/avgPrice/impressionIndex/competition`）、1541=词对比。探针：`probe_insight_api.py`（抓 XHR 清单）、`probe_insight_body.py`（抓完整响应体）。

**CDP 挂死高发**：重负载长跑（数小时）后 `connect_over_cdp` 超时（HTTP /json 仍通）= 浏览器级 CDP 死了，精准杀 9222 + 清 Singleton + 窗口模式重启即可恢复，登录态在 profile 里不丢。**前兆：脚本 0% CPU 空转 + 冒出流浪标签（1688 notfound / taobao.com）**——见到就杀别等。
