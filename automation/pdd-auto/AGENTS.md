# pdd-auto/ AGENTS.md

淘宝穿戴甲 → 拼多多铺货。CDP 9224（发布，窗口模式），采集走 9222（淘宝/千牛）。
Python 3.9，`automation/venv/bin/python`。探路详情见 `pdd_notes/`。

## Phase 0 探路结论（2026-09-30）

- 登录：`mms.pinduoduo.com/login` 扫码一次，登录态存 `chrome-profile`（独立 profile）。
  窗口模式必须可见才能扫码（首次用 `--window-position=0,0`，跑批再离屏）。
- 发布入口**不是** `/goods/publish`（会重定向到商品列表），而是 **`/goods/category`**。
- 发布是两步：**Step1 `/goods/category`**（*主图 + *标题 + *商品分类）→「下一步, 完善商品信息」→ Step2 完整表单。
- Step1 控件：
  - 主图：`input[type=file][accept="image/jpeg,image/png"][multiple]`，Playwright `set_input_files` 可传；要求 1:1 或 3:4、>480px、<3M、≤10 张。上传后显示 `(n/10)`。
  - 标题：`input[placeholder*="商品标题组成"]`，≤30 汉字（60 字符）；页面有「AI生成标题」。
  - 分类：默认给「推荐分类」，含 **`彩妆/香水/美妆工具 > 指甲贴/穿戴甲 > 机器穿戴甲`**（另见 美甲钻/美甲工具）；有「查看更多推荐」。
  - 下一步：文本「下一步, 完善商品信息」。
- **类目选择（已打通）**：推荐区是**异步**生成的——标题填完后按 `Tab` 触发，且渲染有波动（需轮询等 `推荐使用以下分类`）。
  默认只给 3 条；目标 `彩妆/香水/美妆工具 > 指甲贴/穿戴甲 > 手工穿戴甲` 通常要**点「查看更多推荐」展开**才出现。
  点法：`evaluate` 里按 `textContent.trim() === 目标全串` 找元素，JS `.click()`（Playwright `get_by_text` 会卡 actionability）。
- **Step2 全表单**：选类目后「下一步」跳 `https://mms.pinduoduo.com/goods/goods_add/index?type=add&from=category&version=predictCate&id=<catId>&goods_id=<gid>`。
  结构：1 基本信息（*商品轮播图/辅助图/白底图/长图、*商品标题、商品属性 甲型/制作工艺/上市时节/适用人群/风格/图案/产品类型/适用部位/适用肤质/包装种类/品牌/产地/商品资质/包装标签图、商品视频、商品详情）
  / 2 规格与库存（尺码 XS/S/M/L、*价格及库存=库存+拼单价+单买价、*商品参考价、*满件折扣）/ 3 服务与承诺（*承诺发货时间、7天无理由）/ 底部 **提交并上架 / 保存草稿**。
- 运行环境提示：venv 的 PIL 是 x86_64（arm64 Python 用不了），生成测试图改用纯 Python PNG（见 git 里的探路脚本）。

## 上架前合规闸门（2026-10-05 落地，别再手工扫）

```bash
../venv/bin/python sync_compliance_rules.py         # 从技能目录同步词表进仓（缺失会报错，不静默）
../venv/bin/python sync_compliance_rules.py --check # 有漂移退出码 1
../venv/bin/python create_pdd_product.py --source 1688 --preflight   # 只跑闸门不碰浏览器
../venv/bin/python audit_pdd_catalog.py             # 存量体检报告 -> pdd_notes/catalog_audit_*.md
```

- 词表进仓：`compliance_rules.json`（来源/技能版本/同步时间写在 `_meta` 里），闸门只读仓内那份；
  技能装在用户本地，路径一挪就失效，**规则库缺失时闸门抛错而不是放行**。
- 判据在 `pdd_compliance.py`：品牌词（`BRAND_WORDS` ∪ 驳回台账派生）+ 广告法极限词 + 化妆品功效词
  + 平台红线词。纯 ASCII 词按词边界匹配（否则 `involves` 里的 `lv` 会误杀），重叠命中只留最长那条。
- **命中都带 6 字上下文**：中文没有词边界，实测 `欧美白法式` 会凑出「美白」——
  判据不放宽（放过真功效宣称更贵），但报告里写成 `医疗功效:美白（…欧美白法式…）`，人两秒能判。
- 接入点：`build_pdd_worklist_1688.py`（生成队列就剔）+ `create_pdd_product.py`（**连浏览器之前**再拦一次，
  不合规记 `failed` 继续下一件）。被拦的件不占页面、不产生草稿、不消耗风控额度。
- 存量体检只读：不改标题、不改价签、不下架，改不改由人拍。
- 词表本身也先用已知坏样本自证过再信它的「0 命中」（`全网最低价/100%/官方正品/美白祛斑/第一名` → 必报 6 处）。

## 图源风险（重要）

- 淘宝侧美甲主图已有 **86 个**被平台标记（`sourcing/美甲待换图清单.txt`，PIC_STEAL）。
  PDD 对盗图/重复铺货同样敏感 → 铺货前必须确认图源是否为自有图；源是 1688 供应商图则 PDD 端有同样风险。

## 提交成功 ≠ 审核通过（2026-10-05 用店铺反查出来的）

- 成功页 URL 里的 `wait_audit=false` 只代表**提交被受理**，拼多多之后仍可能驳回。判"这件到底上没上"要看
  `/goods/goods_list` 的**在售**列表：10-05 上午实测台账 199 条 → 在售 194 + 已驳回 5，一条不差。
- 驳回全因**品牌管控**（要提交进货发票/品牌授权链路）：`克罗心`×3、`奶芙芙`×2。
  **`奈姿` 是清白的** —— 它是 1688 供应商名，在售 256 条里 72 条带它。别因为驳回标题里出现了它就一起拉黑，
  那两个词才是触发词。已写进 `pdd_config.BRAND_WORDS`，`build_pdd_worklist_1688.py` 重跑时自动剔（本次移走 4 条）。
- 所以：**每铺完一批要回店铺核对在售数**，不能只信 `done` 清单。走法已固化成 `sync_pdd_store.py`
  （抓在售 + 已驳回 + count 接口，落 `pdd_store_snapshot.json` / 累积 `pdd_rejections.json`）。
  注意 `POST /vodka/v2/mms/query/display/mall/goodsList` 要 anti-content 头，直接 fetch 走不通；
  只能开 `goods_list` 翻页抓 `tr`（每页 10 条，`li[class*=pagerItem]` 按页码点）。
- **「已驳回」Tab 是临时的**：2026-10-05 上午还是 5 条，下午同一 Tab 变 0 条，且没进"已删除"(仍是 8)。
  所以驳回原因必须看到一次就落盘 —— `pdd_rejections.json` 按 goods_id **只并不清**，
  品牌词提名(`candidate_brand_words`)读的是这份累计台账，不是今天这一屏。
  提名规则：只出现在驳回标题、在售 256 条里查无此词、且命中 ≥2 条；子串会被母串吃掉。
  **提名 ≠ 拉黑**，要人确认后再进 `BRAND_WORDS`（奈姿那次误判的代价就是 751 条货源）。

## 验证码 ≠ 风控（2026-10-05 修的死锁）

旧版把"弹验证码"和"账号被限流"都返回 `risk` → `sys.exit(42)` → 外层冷却后从**同一件**重试，而那件永远排队首。
10-02 17:10~21:04 整条队列就在 `966442252934` 上空转了 4 轮，**每轮都把表单填到底再卡在验证码上，
草稿箱因此多出两条同名草稿** —— 重试在这条链路上是有副作用的（= 建了重复商品）。

现在：`publish_one` 多返回一个 `captcha` 状态；`record_captcha()` 计数，第 2 次直接隔离进 `failed`，
跳过继续铺下一件；只有**连续 3 件**都要人工过验证才判为账号级风控退出冷却。
节奏常数在 `pdd_config`：`ITEM_GAP_SEC=25`、`CAPTCHA_QUARANTINE_AFTER=2`、`CAPTCHA_STREAK_STOP=3`、`CAPTCHA_BACKOFF_SEC=120`。
离线自检：`../venv/bin/python test_pdd_flow.py`（主循环其余分支要动真实店铺，没法离线验）。

## 事件等待 ≠ 把 sleep 换成轮询（2026-10-05 实测）

把 `reach_step2` 里的固定 sleep 换成"条件成立就走"之后，单件从 **36s 变成 46s —— 更慢了**。
原因不是等待本身，而是**流程跑到了页面前面**：上传指示一出现就立刻 `fill` 标题，
页面自己的异步逻辑随后把值清掉 → `Tab` 白按 → 类目推荐区整页不渲染（等 30s 也不出现，
而同一件商品在网络探针里 3 秒就有）。`wait_until` 吞掉 evaluate 异常也没救，失败计数为 0
说明条件是真不成立，不是报错。

改法是**回读校验 + 重填重试**（`ensure_category_recommendations`）：填完先读回输入框的值，
不一致就重填再按 Tab，最多 3 轮。改完 **36s → 19~20s**。
教训：异步页面上的"加速"必须带自校验，光换等待原语会把等待时间换成超时时间。

## 主图上传被 PDD 前端更新打断（2026-10-09 修复）

**现象**：10-08 之前 12/12、24/25 正常；10-08 PDD category 页换了前端（资源版本 `v20261008111907`）后，
**单件全部**卡在「标题没落进输入框(读回=) → 15s 超时 → 未进入 Step2」，单件 41s 空转。
网络探针显示 `set_input_files` 之后**一个上传请求都没发**（`(0/10)` 不动），不是账号/验证码问题。

**根因两条**：
1. 上传控件不再响应 Playwright 合成 `change` —— 必须在 `set_input_files` 之后再显式
   `dispatchEvent(new Event('input'/'change',{bubbles:true}))`，且文件要**等 React 挂载完成**再 set
   （页面内置的异步逻辑会丢弃太早塞进去的文件；实测 `goto` 后立刻 set 会被丢，等 ~4s 就稳定）。
2. 老代码等计数用的正则 `\(\d+/10\)` **把 `(0/10)` 也匹配掉**，等于上传失败也秒过、从不报错。

**修法**（`reach_step2` + 新 `upload_images`）：`goto` → 等 `input[type=file]` → **sleep 4s** →
`set_input_files` → JS 派发 `input`+`change` → 等 `\([1-9]\d*/10\)`（n≥1）。
上传成功后类目推荐 1s 即出，单件 **41s → 16~22s**。改完 `--test --limit 1` 实测到 Step2、正式跑 `✓ 已上架`。

> 这解释了一个历史误判：「未进入 Step2」不全是"类目推荐没给到目标类目"，很可能是**主图根本没传上去**
> （PDD 没图就不生成推荐）。下次见批量「未进入 Step2」，先看日志有没有 `(0/10)`。

## 本地图缓存（占盘 2026-10-03 清过一次）

- `pdd_images/`（淘宝源，486M）**已删**：这条线被 1688 源替代，89 件的图早已上传到 PDD，本地副本无用。
  `pdd_worklist.jsonl` 仍留着且指向已不存在的绝对路径 —— 要回淘宝源必须先 `build_pdd_worklist.py` 重建（原图 URL 在 `taobao_product_data.jsonl` 里，公网直连可下，不需 Chrome/登录）。
- `pdd_images_1688/`（185M）**保留**：`run_pdd_1688.sh` 不重建 worklist，直接按绝对路径读图，删了会在上传步骤逐个失败。
  真要腾空间：删目录 + 恢复时先跑 `build_pdd_worklist_1688.py`（`cbu01.alicdn.com` 去 `.310x310` 还原原图，实测 200 + 真 jpeg，同样免登录）。
- 这两个目录都在 gitignore 内，不是仓库内容，删不影响 git 历史。

## 发布闭环（2026-09-30 打通的坑，勿重复踩）

- **主图尺寸是最大坑**：PDD 未编辑商详时会把轮播图自动填进图文详情，而**商详校验要求图片宽 480-1200px、高 ≤1500px**；
  淘宝原图常 ~1800px → 点「提交并上架」后被 toast「商详装修校验:请重新上传第N张图片…」**静默拦截**（页面不报错、按钮不禁用、顶部仍显示「错误(0)」）。
  修法：下载后统一缩到 **1080px**（`build_pdd_worklist.py` 用 `sips -Z 1080`）。1080 同时满足轮播图 >480px 与商详 ≤1200px。
- 原图还原：淘宝主图 URL 去掉 `_320x320q80_.webp` 后缀；下载必须带 `Accept: image/jpeg`，否则 CDN 返回 webp（PDD 只收 jpeg/png）。
- 价格：**拼单价 = 淘宝价 ×1.3**；**单买价必须 ≥ 拼单价 + 1 元**（否则报「单买价至少比拼单价高1元」）；商品参考价须 > 最大单买价。
  **商品参考价是会给消费者看的划线价**：代码里 = 拼单价 × `REF_PRICE_FACTOR`(1.5)，而这些新品一件成交都没有。
  按《明码标价和禁止价格欺诈规定》第十六/十七条，这属于「无依据或无从比较的被比较价格」，
  2026 年多地市监就虚假划线价罚过款。收口方式与经营取舍写在 `pdd_config` 注释和 `docs/ECOMMERCE_RULES.md` §2 ——
  改一个常数就行，但那是经营决定，别当技术问题静默改掉。
- 规格：进 Step2 后点「全选以下规格值」（尺码 XS/S/M/L），价格表 4 行每行前 3 个 input = 库存/拼单价/单买价；**每行必须传「预览图」**（循环用主图）。
- 属性：点 **「一键复用」** 自动复用 PDD 相似品属性（填写率可到 91%），无需逐个选。
- 服务：勾「7天无理由退货」（该类目强制）；发货时间选「48小时发货及揽收」。
- **提交是异步的**：点「提交并上架」后要**轮询**；成功标志 = URL 跳到 `/goods/goods_add/success?goods_id=...&wait_audit=false`（`wait_audit=false` 即直接上架）。
  「保存草稿」另走 `.../goods/commit/action/edit`。判定**只认 URL/接口，不认正文关键字**（正文里满是「发布成功…」帮助文案，会误判）。
- venv 的 PIL 是 x86_64（arm64 Python 用不了），缩放改用 `sips`；生成测试图用纯 Python PNG。

## 铺完一批必做的两步（2026-10-05 起）

```bash
../venv/bin/python sync_pdd_store.py            # 抓在售+已驳回 -> 快照与驳回台账
../venv/bin/python import_pdd_products.py       # 按快照登记 platform_product + 1688 货源绑定
../venv/bin/python audit_pdd_catalog.py         # 存量合规体检（只读，出报告）
../venv/bin/python sync_pdd_store.py --check    # 只对差额，不覆盖快照
```

没有第二步，后台永远只有 4 件拼多多商品而店里有 231 件（2026-10-05 实测就是这个差）。
`import_pdd_products.py` 认两条码：1688 直铺批次的 `item_id` 就是 offerId（进价取 worklist 的 `cost`），
淘宝源批次要能在 `sourcing/isv_offer_taobao_map.jsonl` 里查到货源，查不到就跳过并报数。
快照缺失时它不做在架过滤（会打印一行警告）—— 先跑 sync 再导，别反过来。

## 定价：生效的是 ×5，不是成本倒推那组常数

`build_pdd_worklist_1688.py` 用 `pdd_price_markup`（进价 × `PRICE_FACTOR_1688`=5.0）。
`pdd_price_cost` 那条成本倒推（快递 3 / 费率 0.6% / 损耗 3% / **目标毛利 40%**）目前只有单测在调，
所以**改 `TARGET_MARGIN` 不会改任何在售价**。×5 在 0.6% 服务费下的毛利率恒为 79.4%，
运营台"预估毛利"列显示的就是这个数（231 件全是 79.4%，因为价格与进价严格成正比）。
要真换成成本倒推得先确认 40% 这个目标是他定的 —— 那会把已上架 146 件的价格口径换掉。

## 2026-10-05 实测台账

在售 231（今日 +36）· 已驳回 5（全是品牌词，见上）· 草稿 16 · 审核中 16。
`pdd_products.jsonl` 235 行 = 在售 231 - 1（人工建的 1012038274196）+ 5（驳回）。
今日两轮 12/12 与 24/25，零验证码；唯一失败是 `892967120772`「未进入 Step2」（类目推荐没给到目标类目，
可 `--retry-failed` 单件重试）。队列剩 892。
