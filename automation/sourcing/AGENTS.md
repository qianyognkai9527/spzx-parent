# sourcing/ AGENTS.md

1688选品→抖店/淘宝铺货自动化。CDP驱动，Playwright async，Python 3.9。

## Chrome实例

| 端口 | 用途 | 启动 |
|------|------|------|
| 9222 | tb-auto（1688 ISV SPA） | `tb-auto/run_chrome.sh` |
| 9223 | sourcing（抖店+1688） | `sourcing/run_chrome.sh` |

**9223同时登录了抖店和1688 ISV**。同一Chrome上不要并行跑两个1688 CDP任务（会互触风控）。`cdp_utils.py`的`connect_cdp(port)`统一连接+清理孤儿tab。

## 关键数据文件

| 文件 | 内容 | 行数 |
|------|------|------|
| `douyin_product_data.jsonl` | 1688商品详情（offerId/title/source_price/main_imgs/detail_imgs/sku） | 1820 |
| `douyin_worklist.jsonl` | 轻量worklist（offerId/title/source_price/img_uris/consign） | 1820 |
| `draft_match.json` | 草稿箱匹配结果（product_id↔offerId↔source_price） | 1005 |
| `relist_progress.json` | 批量上架进度（done/failed） | - |
| `sourcing_raw.jsonl` | 1688搜索原始数据 | - |

## 批量上架流程 (batch_relist.py)

**核心流程**：删草稿→编辑已发布版本→改价格→填面料→填尺码表→发布

1. **删草稿**：打开`/ffa/g/create?product_id=xxx`，检测"已存草稿"→点"删除草稿"→确认
2. **改价格**：`td:has-text('价格￥') input.ecom-g-input-number-input`，用`fill()`设值
3. **填面料材质**：点`[data-kora="click_multi_value_measure_composition_select"]`→搜"聚酯纤维"→勾选→填100%→Escape关闭。**已有面料需先清除**（含量总和>100会报错）
4. **填尺码表**：disabled input不能用fill/type。**用React fiber的`fieldFormNode.setValue()`**：
   ```python
   page.evaluate("""(data) => {
       const inputs = document.querySelectorAll('input[placeholder="推荐填写"]');
       for (let i = 0; i < inputs.length; i++) {
           let fiber = inputs[i][Object.keys(inputs[i]).find(k => k.startsWith('__reactFiber'))];
           for (let j = 0; j < 20; j++) {
               if (!fiber) break;
               if (fiber.memoizedProps?.fieldFormNode) {
                   fiber.memoizedProps.fieldFormNode.required = false;
                   fiber.memoizedProps.fieldFormNode.setValue(data[i]);
                   break;
               }
               fiber = fiber.return;
           }
       }
   }""", ['150-155','80-90','155-160','90-100',...])
   ```
5. **发布**：JS click"发布商品"→循环处理弹窗（"不修改，继续发布"/"推荐有误"等）→检测`发布成功`或`线上商品数据已更新`

**成功标志**：页面显示"商品发布成功，线上商品数据已更新"。仅显示"商品信息质量 及格XX"不算成功。

## 抖店编辑页坑

- **虚拟滚动表格**：价格input可能不在视口内，需先`scrollIntoView`再`fill()`
- **React受控输入**：`fill()`有效，`type()`/键盘输入会被React重置
- **面料百分比**：`fill('100')`前需先清除已有面料（否则总量>100报错）
- **弹窗链**：发布后可能连续弹出尺码表→品牌→确认，需循环处理
- **草稿vs已发布**：编辑已存在的商品时，如果已有草稿会加载草稿数据。必须先删草稿再编辑

## 抖店直建 create_douyin_product (2026-09-10 调通)

- **规格图设置 drawer**：SKU Excel 智能识别后自动弹右侧 `ecom-g-drawer-open`，拦截属性区所有点击（Playwright click 全超时）→ `close_drawer()` 点 `.ecom-g-drawer-close`，在填适用性别/面料前必须关
- **适用性别必填**：多选 tree-select（女/男/男女通用），`div[attr-field-id="适用性别"]`，选「女」；验证值读 `.ecom-g-select` 文本
- **尺码表(尺码助手)必填**：类目要求身高+体重，否则提交被「请填写尺码表或在图文详情中上传尺码信息」拦。输入框被 `styles_layoutContainer`(overflow:hidden) **内部裁剪** → Playwright click/fill 全部超时，唯一路径 = JS `scrollIntoView`+`focus()`+`keyboard.type`；输入框**只收纯数字**（`-`/`~` 全被吞），用单值（如 S=157/51）。行结构：`请输入`(尺码名,自动带出) + 2×`推荐填写`(身高/体重)
- **提交弹窗链**：`不修改，继续发布`(尺码模板不一致提醒)→`推荐有误`(品牌/类目推荐)→…须循环轮询处理（参照 fix_douyin_images.publish 模式，24×3.5s）；product_id 从 **createWithSchema** 响应拦截（旧 on_resp 只抓 /product/|/tproduct/|/schema/ 漏了它）
- **类目建议拦截（间歇）**：提交时 AI 改判「情趣内衣(未开通)」→ 内联 has-error 拦提交，无法绕过 → save_failed 下轮重试（间歇性，会过）；选类目阶段推荐情趣内衣 → 跳过 create_failed（推荐随机，重试会过）
- **判定以保存响应/页面成功标志为准**；「请选择/请填写」正文检查会因可选属性占位符误报，勿用
- **10001010A「当前环境存在风险」≠失败**：仅 publish API 警告，后续弹窗链处理完仍可能发布成功（2026-09-10 实测 07:20 案例），以最终发布判定为准；频率高时属账号级风控苗头，勿因此中断循环

## 风控

- 1688搜索：~5次快速加载→0结果（throttle），source_1688.py自动冷却25min
- 抖店发布：频繁提交触发"被挤爆啦"，需降速（每商品≥30s间隔）
- API重放检测：`editWithSchema`直接重放会被拦（`10001010A`错误），必须走UI

## MySQL

`localhost:3306`, user `root`, 库 `db_spzx`；**口令不在脚本里**——`dbconf.py` 读 `~/.spzx/db.cnf`（由 `python3 scripts/mysql-cnf.py` 生成）。CLI: `/usr/local/mysql/bin/mysql`。启动需`launchctl load`（见tb-auto AGENTS.md）。

## 1688选品流程

`source_config.py` 配置类目/关键词/价格门槛。**CDP_URL=9222**（用tb-auto的Chrome，与抖店9223分流）。

- `source_1688.py`：搜索1688→抓商品卡片→存`sourcing_raw.jsonl`（支持`--kw`/`--pages`/`--test`/`--finalize`）
- `import_to_db.py`：JSONL→MySQL（`source_product`+`source_factory`），调`grade_quality.py`评级。
  ⚠️ **它有几列是写死占位的，别当成"这家货源没数据"**（2026-10-04 按 5373 行实测填充率核过）：
  `eval_with_image_count` INSERT 里直接写 `0`（全库 5373 行恒 0，没有任何采集器填它）；
  `logistics_name`、`dispatch_time` 全库 100% 空；`source_product_sales_history` **0 行**
  （所以"近14天销量"派生不出任何东西）。真正在采的只有
  `repurchase_rate`/`trust_years`/`sales_count`（1707 行，32% 覆盖）、`steady_status`、`category_name`（50%）、
  `quality_grade`（186 行）。前端 `production.vue` 已把"带图评价数"标成"(未采)"并在表头上方挂了说明条。
  评价缺口页（`EvalGapMapper`）的"货源带图评价数"用的就是这个恒 0 列 → **缺口恒等于 0，该页没有数据地基**（菜单也已停用）。
- `fetch_freight.py`：补抓运费（CDP 9223，`--limit`/`--test`）
- `grade_quality.py`：纯DB评级，幂等全量重算

## 纯DB任务（无需Chrome）

`grade_quality.py`, `clean_titles.py`, `detect_alerts.py`, `sync_isv_to_platform.py`, `guess_sku_bind.py`, `import_to_db.py`, `assess_visual.py`, `assess_main_img.py`

## ISV 铺货失败编辑 (edit_isv_drafts.py, 2026-08-29)

淘宝 ISV 铺货失败商品自动编辑提交脚本。CDP 9222，读 ISV 铺货失败列表，逐个"编辑店铺草稿→继续上架→填穿戴甲表单→提交"。进度 `isv_edit_progress.json`（done/failed 数组，脚本只处理两个数组里都没有的 row_key）。

**2026-08-29 结论: 38 个失败项全部标记 done 跳过 + 已从 ISV 铺货失败列表手工清掉**（失败原因备份在 `isv_edit_progress_backup3.json`；ISV 侧确认 `铺货失败(0)`、`全部(1012)=铺货成功(1012)`，任务关闭）。原因是:

- **~32 个穿戴甲商品: SKU 颜色值带 1688 元数据 → 淘宝"颜色分类填写错误"**。1688 源 SKU 颜色格式是 `颜色名【系列】【SKU-ID】`（如 `XS 珍妮【细狗尖】【950】`），淘宝颜色分类字段拒绝含 `【】` 的值，提交被表单校验拦截（错误上下文: `优化建议 错误(1) 销售信息 颜色分类 填写错误`）。成功的那 149 个商品颜色值是干净的。
- **6 个非穿戴甲商品**（美甲胶水/指甲装饰组合，如"固态贴片胶+光疗灯组合"）：类目不同，页面没有款式/适用场景/规格字段，硬编码 `struct-p-657638213/657638215` 找不到 → "缺少字段"。

**修复尝试失败记录（勿重复踩坑）**:
- 直接改 React fiber 数据（`changeElementValue('sku', newVal)` 清 `【】`）**不持久化**——SKU 表 store 从源数据(`saleValueList`/`dataSource`)重新派生，改动被覆盖，DOM 不重渲染，提交仍报错。
- 点击 SKU 单元格/颜色分类筛选下拉/批量填充按钮均无编辑入口。
- 结论: 这些商品需**人工在浏览器里删 SKU 颜色里的 `【系列】【SKU-ID】`**，或用正确的方式重构 SKU 维度（颜色分类 × 大小，勿合并）后才能提交。

## 店铺中分类批量归类 (assign_shop_category.py, 2026-08-29 进行中)

淘宝仓库商品批量设置「店铺中分类」到 8 个店铺类目（家居服/睡衣、牛仔短裤、秋冬款、连衣裙、长裤、半身裙、美甲、other）。CDP 9222，编辑页 `item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true`。

- `collect_in_stock_current.py`：重采当前 in_stock 列表 → `taobao_in_stock_current.jsonl`（翻页必须点"下一页"，goto ?current=N 无效；断点续跑按 itemId 去重；**复用已打开的 in_stock 标签页会误关用户页面**，用 `--restart` 强制回第 1 页）。
- `--list sold_out`：采出售中列表 → `taobao_onsale_current.jsonl`（tab 计数设页数上限防越界，千分位计数如"1,840"已兼容）。
- `build_shop_cat_plan.py`：标题关键词 → 8 类目 → `shop_cat_plan.json`。优先级（已与用户确认）：美甲→牛仔短裤→秋冬款（**含"秋冬/加厚/毛绒"的睡裙也归秋冬款，优先于家居服**）→半身裙→连衣裙→长裤（**排除套装词**：含睡裙/睡衣/家居服/吊带裙/胸垫/外袍等不进长裤）→家居服/睡衣→other。纯货号垃圾标题归 other。`--merge` 合并重建（旧判定保留 + 新商品 classify，plan 带 pool 字段 onsale/warehouse/gone）。
- `assign_shop_category.py`：批量编辑+提交宝贝信息。进度 `shop_cat_progress.json`（done/failed/skipped）。`--test`/`--limit N`/`--start N`/`--retry-failed`/`--worker K N`（K/N 分片并行，**见下：不推荐**）。
- `assign_shop_category_v2.py`（v2，2026-09-24 起扩大覆盖在售商品）：`--test`/`--limit N`/`--start N`/`--retry-failed`/`--ids id1,id2`（定向选取，**可补跑 skipped，done 仍跳过**；gone 池商品无 `--ids` 时自动剔除）。进度 `shop_cat_v2_progress.json`（done/failed/skipped/noprice/sizegap）。skipped 美甲见下方「穿戴甲脏色清洗」。
- **合规填充器**（2026-09-25）：平台新增按类目必填（SKU 厚薄/是否加绒/款式，属性 面料/上市年份季节/是否商场同款/功能/适用场景），v2 提交前自动检测填充（compliance_filler.py，页面自带错误态零试提交）；新浮层（sku-preview-iframe/struct-error-board）拦点击，clear_overlays 必须在一切交互前；提取方式 JS click 不稳定（r1-D 实证有时生效）改真点击；提交失败仅剩 PIC_STEAL → 转 skipped 待换图。探路修正：**#struct-error-board 被 clear_overlays 隐藏后 innerText 读不到**（提取方式类错误只在此板出现），detect_gaps 须临时还原读 board；**SKU msg-bar 一次只报行内首缺字段**（裤型→裤长级联），填充须 detect→fill 迭代至清零（3 轮成功上限）；长裤类 裤型/裤长 也是必填 SKU 列（已入 FIELD_ZONE，取值=标题含选项名/公共子串优先，无匹配留人工不写猜测值）；SKU 多选（next-select-multiple）弹层不自动关须 Escape、写回态="… "+tag 文本按含值校验、占位符"请选择"不算已有值；v2 `save_progress` 的 failed 磁盘合并是纯增量，转 skipped/done 后必须剔除否则旧档复活（已修）。⚠ 运行中改 filler/v2 代码**不热生效**（正常完成即退出循环，须等 exit 42 冷却轮重启或手动重启 wrapper）。
- **B/C 深夜探路**（2026-09-26 深夜，failed ②销售规格 238 + ③属性 89 突破）：**①残留 next-overlay 弹层拦一切点击**（单选选完不关/页面自带弹层）= 裤长/提取方式/属性全 8s 超时的根因 → `ensure_no_overlay`（Escape 循环清残留）加在 fill_extract_way/fill_sku_gaps 每行/fill_prop_gaps 每字段前；**②combobox 列值写进内部 input.value**（裤长实证，select 文本恒空）写回校验须读 input；**③新必填字段**（均实地核读选项后加规则）：属性 适用人群（大码胖→特殊体型女性/运动→运动爱好者/学生→青少年女性/兜底成年女性）、风格（标题匹配兜底休闲风）、是否带胸垫（含"胸垫"→是）；SKU 列 裤长（公共子串+语义别名 直筒/阔腿→长裤，无匹配留人工）、裙长（兜底中裙）、适用体型（兜底通用型）、图案（兜底纯色）。8 样本跨 6 品类全部面板清零（test_bc_rules.py 25 断言）。注意：**面板分节只报计数不报字段名，未知字段名在内联 msg-bar**（格式"SKU行名：字段不能为空"，冒号后才是字段名）；failed 里部分是过期失败（规则补齐前挂的，重试即过）。

- **穿戴甲脏色清洗**（2026-09-26）：SKU 颜色值带 1688 元数据【甲型】（如 `XS 黑粉千金【细狗尖】`）→ 淘宝「颜色分类填写错误」。**08-29"程序不可改"结论已被推翻**：「编辑规格」对话框主色 input 可编辑，确认创建重建 SKU 表实测**保留价格/库存/已填参数值**（3 样本含 8 SKU 双甲型）。`compliance_filler.clean_sku_color_brackets`：【x】→`-x`（保留甲型防重名，只去被拒括号）；清洗后重名/空值/无按钮 → `CLEAN_MANUAL` → v2 转 skipped。**顺序红线：重建后错误检测被遮蔽（detect_gaps 报不出缺失）→ 必须先在原表跑 `run_compliance_fill`（process_one 内重构出的 detect→fill 迭代）再清色重建**。美甲最小必需集=**仅款式**（大小/风格/色系/图案非必填勿乱填；款式走现有标题匹配+首项兜底规则）。E2E 实证 2 样本提交通过颜色/规格校验，仅剩 PIC_STEAL（主图盗图，1688 供应商图）→ 754 个 onsale 美甲批量解锁的最终卡点=换主图。

**关键机制（勿再踩坑）**:
- **属性推荐弹框「商品属性信息更新确定」必须点「确定」**。⚠️ 弹框容器是 **`.next-dialog`**，不是 `.next-dialog-wrapper`！且它是 position:fixed，**`offsetParent` 恒为 null** → 检测可见性必须用 `getClientRects().length > 0`，用 `offsetParent` 会永远检测不到（这是本任务最深的坑，曾导致弹框从未被处理）。点击用 Playwright locator（`dlg.locator('button', has_text='确定')`），JS `.click()` 对 React 不可靠。弹框在页面加载后/滚动时可能弹出，进编辑页后、滚动后、提交前都要调用处理函数。
- 店铺中分类：`#sell-field-shopcat` 展开扁平 8 节点树，勾 `.next-tree-node` 内 `.next-checkbox-wrapper`，清空已有勾选后勾目标；校验 `#sell-field-shopcat .next-tag` 文本。**淘宝已把该树节点「长裤」改名为「休闲裤」（2026-10-09 用户确认）**：内部 plan/分类桶仍叫「长裤」，`assign_shop_category.py` 的 `SHOPCAT_ALIAS={'长裤':'休闲裤'}` 在写入树前映射，别去改 plan 或进度文件。症状=批量 `类目设置失败: 目标类目[长裤]不在树中`（被 `is_permanent_failure` 判永久、`--retry-failed` 跳过，要补跑须先把这些 failed 条目从 `shop_cat_v2_progress.json` 删掉，或 `--retry-failed --ids` 同时传）。
- **提交成功判定以 `submit.htm` 响应体为准**（`globalMessage.type=success` → 跳 `sell/v2/success.htm` 或页面"商品提交成功"）；页面文本/URL 不可靠。提交后可能有「继续发布」/「前往查看」违规弹窗（详情图含尺码信息自动填表提示），点后部分需**二次点提交**。
- **尺码表报错处理**：响应 `CHK_SIZE_ROW_IS_EMPTY` 或页面"商品尺寸表 必填项未填" → 清空商品尺寸表（`#sell-field-sizeMapping` 内「一键清空」）后重新提交。尺码表**要么全填要么不填**；个别类目尺寸表为硬必填（清空仍报错）→ 标 skipped 待人工。
- 提取方式（`#sell-field-tbExtractWay`）默认已选"使用物流配送"，未选时点第一个选项。
- 上架时间（`#sell-field-startTime`）读当前状态**原样维持**：仓库商品保持「放入仓库」、在售商品保持「立刻上架」，不碰 radio 防误上架；2026-09-24 起支持在售商品（探路验收通过）。
- **每商品必须 `ctx.new_page()` 新开 tab**（SPA 同 URL goto 不重渲染），用完只关自己的 tab；用 `connect_cdp(9222, keep_urls=["myseller.taobao.com","item.upload.taobao.com"])` 保护用户页面。
- **永久失败项不再自动重试**（2026-10-07）：`compliance_filler.is_permanent_failure` 判 `数据问题`/`PIC_STEAL`/`CHK_VIDEO_RATIO_INVALID_ERROR`/`类目设置失败` 等永久失败；`build_todo` 在 `--retry-failed` 下剔除它们（启动日志 `失败 N(永久M不再自动重试)`），只重试瞬时失败（超时/网络/假失败）。要补跑永久项用 `--ids id1,id2` 显式定向（`--ids` 可放行 skipped/failed 的永久项）。
- 节奏（2026-08-30 提速后）：间隔 3-5s、每 30 个休息 25-35s。实测单商品 ~60-80s，其中大量时间花在等 submit 响应/弹框处理。
- **Chrome 9222 target 耗尽**：长跑后 CDP 浏览器接口活着但 `/json/list` 返回空，playwright 连接报 `Browser context management is not supported` → `pkill -f "remote-debugging-port=9222"` 后重启（**窗口模式** `--window-position=-32000,-32000`，勿用 run_chrome.sh 的 headless，淘宝 session 在窗口模式才保持；重启后登录态保留）。**2026-10-08 起 `run_cat_v2.sh` 会在非风控退出且末段日志含连接错时自动执行这套重启再续**（此前遇 `exit code=1` 会静默结束、曾停摆 9 小时）。

### 淘宝品牌/标题批处理（edit_brand_title_batch.py, 2026-10-07）

淘宝「睡衣/家居服」店铺分类商品：设品牌=瑰若 → 导购标题 AI → 主标题 AI（须瑰若开头）→ 提交，**原上下架状态不变**（不动价格/店铺分类/SKU/图片）。CDP 9222，清单 `brand_title_targets.jsonl`、进度 `brand_title_progress.json`，CLI `--enumerate/--test/--limit/--start/--retry-failed/--ids`。**与归类 v2 共用一个淘宝账号的 RGV587 额度，一次只跑一个**。

- **圈选 = 店铺分类筛选**：列表页 `input#queryShopCategoryId` 的 tree-select，**必须点 `.next-tree-node-inner`（`role=treeitem`）才写入值**；点 `.next-tree-node-label`（纯文本 div）是假阳性（回显空、搜索不生效）。选完读 `.next-select-values em` 文本校验。
- **出售中路由 = `SellManage/on_sale`**（`?current=1&pageSize=20`），**不是 `sold_out`**——后者是含仓库项的大视图（实测 4228），会让 `in_stock`(仓库中，3125) 全成其子集被 `dedup_targets` 清空。仓库中=`SellManage/in_stock`。`enumerate_targets` 有「两池 itemId 交集 > 50% 就报错」护栏。
- **品牌下拉是可搜索虚拟列表**：列表本身很短、常不含目标品牌，**光滚动永远命中不了** → 往弹层 `.next-overlay-inner.next-select-popup-wrap input` 输入品牌名，再点 `.options-item[title=品牌]`（`_pick_option_with_scroll`）。
- **受控输入「改 DOM 不写 React 模型」两个坑**（都表现为提交值 ≠ 输入框显示值）：①主标题超 30 汉字/60 字符（服务端 `CHK_BASIC_LENGTH_LONG_BYTE: 不能超过30个汉字或60个字符`）——原生 setter 只改显示不改模型，**必须用 Playwright `fill`**（`#sell-field-title input`）；②**吊牌价（`#sell-field-p-344943689`）是遗留必填**（`fill` 也写不进）——**必须键盘输入**（`click`+`Meta+A`+`type`+`Tab`）。吊牌价按合规口径填**=一口价**（`docs/ECOMMERCE_RULES.md` §2，别做无依据划线价）。
- 提交前复用归类 v2 的 `run_compliance_fill` + `remove_videos`（`from assign_shop_category_v2 import ...`）+ `ensure_extract_way`，补铺货后遗留的必填项（是否商场同款/功能/适用场景等）与删横版视频。

### 双 worker 并行（`--worker K N`，2026-08-30 踩坑后结论：别用）

两路并行等效 ~35s/个 但坑极多，用户已决定回单 worker 串行（稳）。若再用并行必须记住：

- `save_progress` 已加 **fcntl 文件锁 + 磁盘合并**（多 worker 同时写 `shop_cat_progress.json` 不互相覆盖）。
- 两 worker 抢同一 Chrome 渲染进程 → `page.evaluate` 偶发**永久挂起**；主循环已用 `asyncio.wait_for(process_one, timeout=120)` 兜底，超时自动标 failed 继续。
- `connect_cdp` 启动时清孤儿 tab 会**误关另一 worker 正在用的 tab**（keep_urls 没覆盖 item.upload 时）→ 表现为对方 `Target page...has been closed` 然后误判风控进 600s 冷却。启动 keep_urls 必须含 `myseller.taobao.com`+`item.upload.taobao.com`。
- ⚠️ **判分片必须传本 worker 的 todo itemId 集合，勿用 plan 全量索引**：worker 分片是"过滤掉 done/failed/skipped 后的 todo 索引 `%N`"，与 plan 全量索引不一致，用 plan 索引清理会误关对方正在用的 tab（已踩坑）。正确范式：`my_ids = {r['itemId'] for r in todo}` 传给 `cleanup_leaked_tabs`。
- worker 崩溃（见下）后另一路仍会继续写共享进度，重启崩溃那路即可断点续跑。

### 标签泄漏治本（2026-08-30）

提交成功页 `success.htm` 会**弹 1-2 个子窗口** `g.alicdn.com/platform/xdomain-storage/{ver}/frame.html`（跨域存储），`page.close()` 管不到子窗 → 每成功一次漏 1-2 个 tab；`keep_urls` 只在启动时清一次，跑起来后新漏的不再清。长跑会堆到 30+ 标签吃内存，甚至触发「Chrome 9222 target 耗尽」。

- 治本：`cleanup_leaked_tabs(ctx, my_ids)` 每处理完一个商品回收本 worker 分片的孤儿 tab（xstore.insights 纯泄漏直接关；URL 带 `itemId=/primaryId=` 且 itemId ∈ my_ids 的 success/publish/xdomain 全关）。验证：标签数应稳定在 ~8-10 不增长。
- **Node 驱动崩溃特征**：日志出现 `ProtocolError: Page.handleJavaScriptDialog: No dialog is showing` + `Node.js v24.15.0` 异常栈，随后每次操作报 `Connection closed while reading from the driver` → 整个 worker 已死（python 进程还在但空转 600s 冷却），必须 kill 重启。属偶发 dialog 竞态，非风控。

### 淘宝提交风控（2026-08-30 实测）

- 高频提交触发**账号级风控**：提交被拦、页面/响应出现 **RGV587 / x5sec 拼图滑块**，冷却需**数小时-24h**。响应从 `globalMessage` warning 变回正常 = 冷却解除。
- **2026-10-07/08 实测节流曲线：账号级 RGV587 把提交速率封在 ~10 件/小时**——每轮爆发约 22–35 件（跑 ~35 分钟）后被拦，冷却 2h；缩短冷却到 20m/40m 常 0 产出（账号没凉）。**别频繁手动重启 wrapper**（会把冷却阶梯重置成短的，反更慢）；**两个淘宝写任务（归类 v2、品牌批处理）共用一个账号，只能串行**，并行只会更早触发。
- **「提交超时未确认」多为假失败**（实际已提交成功，仅响应确认超时），会进 failed 数组；`--retry-failed` 重试时已成功的会被再次提交（幂等，仅重复设类目）。真风控拦截的特征是响应含 `FAIL_SYS_USER_VALIDATE`/`captchacappuzzle`。
- **一直出验证码时应停止提交等冷却**，不要硬冲。

### 进度与调度（2026-10-08）

- **进度以文件为准**：归类 v2 `shop_cat_v2_progress.json`、品牌 `brand_title_progress.json`——本文档不写会过期的行数。
- **归类 v2 与品牌批处理共用同一个淘宝账号 → 必须串行**；2026-10-07 用户决定**先跑完归类 v2 再开品牌**。
- 续跑归类 v2：`cd automation/sourcing && nohup ./run_cat_v2.sh --retry-failed > /tmp/cat_v2_wrap.log 2>&1 &`（自愈：exit 42 阶梯冷却续跑、CDP 掉线自动重杀/重启 9222）。
- 跑品牌：`nohup /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python edit_brand_title_batch.py > /tmp/brand_run.log 2>&1 &`（先 `--enumerate` 生成清单、`--test` 单件验证）。
- **每完成一件活立即留痕**（`python3 spzx-parent/scripts/log_work.py`）：手做的自动化活不进 `ingest_batch`，不记就只在进度文件里、事后无从按模块排查。长任务用 `--merge` 合并当天同模块同标题一条并刷新进度，零散小活直接追加。样例：
  ```bash
  # 归类 v2 告一段落（文件自动解析 done/skipped/failed）
  python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/log_work.py --module 淘宝归类 \
    --title "归类v2 第N轮" --progress-file shop_cat_v2_progress.json --merge
  # 品牌批处理
  python3 .../scripts/log_work.py --module 品牌标题 --title "品牌=瑰若批处理" \
    --progress-file brand_title_progress.json --merge
  # PDD 直铺
  python3 .../scripts/log_work.py --module PDD铺货 --title "穿戴甲1688直铺" \
    --progress-file /Users/qyk9527/ideaProject/spzx-parent/automation/pdd-auto/pdd_create_progress_1688.json --merge
  # 1688 选品
  python3 .../scripts/log_work.py --module 1688选品 --title "穿戴甲选品" --progress "1061 条入库"
  ```
  模块建议清单：淘宝归类、品牌标题、PDD铺货、1688选品、AI选词、视频生成、对账、小说、系统、其它。详见根 `AGENTS.md`。

## ISV「规格匹配」全量过一遍 (isv_sku_match.py, 2026-10-14)

**用途**：淘宝库存同步走 1688 淘分销，同步是 **SKU 规格级**——淘宝商品每个 SKU 必须与 1688 货源 SKU 1:1 匹配。本脚本把控制台「商品管理 → 已关联货源」**每个商品都过一遍**（已匹配的也不例外）：开「更多→匹配规格」抽屉 → 点「**自动匹配规格**」→ 点「**确 认**」；匹配不全记 `manual_needed`、淘宝 SKU 数≠1688 规格数记 `count_mismatch`、同 1688 规格绑多个淘宝 SKU 记 `sku_duplicate`。CDP 9222。

- **1688 规格数两级来源**：① DB `source_sku`（按 `source_product_url LIKE %offer/<id>.html%` 关联，精确，约 838/4183 覆盖）；② DB 没有 → 读抽屉**规格选择器**（`.spec-select-dropdown`，是「颜色/尺码」radio 组+取消/确认，**不是普通下拉**）radio 组数求积（估算，`spec_source=picker_est`）；③ 再没有 → 不判计数。
- **坑（实测）**：抽屉 fixed 定位，可见性用 `.ant-drawer-open`（勿用 offsetParent）；**关抽屉绝不用键盘 Escape**（事件发到外层页面，iframe 里的抽屉收不到 → 抽屉常开挡住后续一切点击，表现为 `ant-drawer-header intercepts pointer events`）——只走抽屉内「取消」/`.ant-drawer-close`/`.ant-drawer-mask`；快捷筛选 chip 文本带计数后缀（`已关联货源(4183)`）必须**前缀匹配**不能全等；点击失败降级 `force=True`。
- **跑法**：`--limit 2 --dry-run` 预演 → `--limit 1 --apply` 试点（用户盯）→ 全量 `nohup venv/bin/python -u isv_sku_match.py --apply --gap 10 > /tmp/sku_match_run.log 2>&1 &`（4183 个 ≈ 29h，断点续跑）。`--ids` 定向补跑、`--force` 全量重来。
- **报告**：`sku_match_report.json`（按 item_id 续跑，终态=ok/manual_needed/count_mismatch/sku_duplicate 跳过）+ `sku_match_manual.csv`（人工清单）。
- **单测**：`test_isv_sku_match.py`（纯函数：规格名解析/计数与重复判定/报告 upsert/CSV 行，含 picker 估算路径）。
- spec：`docs/superpowers/specs/2026-10-14-isv-sku-match-design.md`。

### 窗口防弹（2026-10-16，用户明令 9222 绝不显示）

- **弹窗两个来源（实测）**：① macOS 把 `--window-position=-32000` 钳回可视区 → Chrome 启动到 CDP 就绪前（~8s）窗口可见；② **`ctx.new_page()` 新开标签会把最小化窗口顶回前台**（探针连开 4 次弹 4 次，用户投诉）。
- **对策**：`cdp_utils.minimize_windows(ctx)`（CDP `Browser.setWindowBounds`，无需辅助功能权限）；`connect_cdp(..., minimize=True)` 连接即压回；`cdp_utils.new_page_quiet(ctx, url)` 新开标签后自动压回；`scrape_isv_offer_taobao.open_page(ctx, quiet=True)` 同理（isv_sku_match 已用）。**注意**：要用户人工拖滑块的场景别 minimize（会把验证码藏起来）。独立 CLI 仍有 `automation/tb-auto/cdp_minimize.py 9222`。
- 排查类脚本纪律：跨站读取复用同一个标签 goto（跨域是整页重载），别开新页；`isv_offer_taobao_map.jsonl` 是旧快照不全，**找商品用「已关联货源」chip + 搜索框搜 ID**（必先点 chip，默认视图搜不到）。

### ISV 全量库存同步 (isv_stock_sync.py, 2026-10-16)

**把 1688 货源库存推到淘宝 SKU**：控制台「已关联货源」逐页（**100 条/页**）表头全选 → 点**「批量同步库存」**（在勾选列旁边那排；用户口中的「全量库存同步」控制台无此名）→ 确定 → 下一页。**控制台没有跨页全选**（表头勾选框只作用本页，勾选列 hover 也没有 extra 下拉），全量=逐页循环。报告 `stock_sync_report.json`（pages 页号→rows），`--start N` 断点续跑，`--dry-run`。

- **验证口径**：行级「同步记录」弹窗（同步时间/内容/结果/方式），SKU 级文案如「商品库存同步为352，M 白色规格库存同步为286」。
- **坑（实测）**：① 同步提交后 `.ant-modal-wrap` 会残留数秒拦翻页/勾选——翻页前必须 `wait_no_modal`；② 提交后页面卡顿会让点击 hang 在 "performing click action"——全选/翻页都要 3 次重试 + JS click 兜底；③ 切 100条/页 的 antd 下拉点击有竞态，点完必须**回读选择器文本**验证、失败重试（force）一次；④ 新开会话每页都回 20条/页，每轮都要重切；⑤ 崩溃残留的弹窗/选中态会污染下一轮——续跑前最好干净导航一次。
- **和 `inventory_cron.sh`（每天 05:00）分工**：**05:00 行仅告警检测，采集已迁 03:00**（`run_stock_refresh.sh` → `detect_stock_change.py --tiered`，见下方「分级刷新」节）；**不推淘宝**；推淘宝 = 本脚本（此前只有手动按钮，用户 9-02/9-12 的同步记录即手动）。
- 单商品抽查方式：「已关联货源」chip + 搜索框搜 ID（必先点 chip，默认视图搜不到）→ 同步记录弹窗。

### 「[已下架]」结论（2026-10-16 实证，样本 1086192871521）

- 抽屉左列「店铺商品规格」带 `[已下架]` 前缀 = **淘宝 SKU 侧**；右列 1688 货源规格全是干净名（`摩卡灰-2XL`，¥32.5/库存2000）。1688 货源页（offer/980287802829）**0 处「已下架」**、规格全在售；淘宝买家页 SKU 名里也没有「已下架」三字 → 前缀是**控制台状态标记**，表示该尺码 SKU 在淘宝店侧已被下架/移除（历史绑定残留），不是 1688 下架、也不在 SKU 名里。
- 含义：`manual_needed` 里 6716 行/616 商品的 `[已下架]` 是死 SKU 的惰性记录，不影响在售链接。另发现自动匹配会把死 SKU 绑错位（XL→摩卡灰-2XL 等），死 SKU 无实害，清理时可顺手「清除」。

### 货源全量建档 backfill_offer_archive.py（2026-10-18，spec 2026-10-18 P1）

**目的**：让 `taobao_offer_map` 的每个 offer_id 在 `source_product`/`source_sku` 都有档（超卖监控的地基，无档=盲区）。两步：`--remap` 零采集补映射（正则 `offer/(\d+)` 扫 `source_product.source_product_url` → UPDATE `taobao_offer_map.source_product_id`）；主跑建档（仍无档的 offer 逐个开 `detail.1688.com/offer/{id}.html`，复用 `offer_fetch` 拦截详情 API，建 `source_product`（`data_source=2`、`platform_type=1`、`freight_cost=8` 定值）+ `source_sku` 行 + 回填映射）。

- **映射即进度**：todo 按 DB 现算（`taobao_offer_map.source_product_id IS NULL` 的 distinct offer_id），**不看进度文件**——中断直接重跑，已建档自动跳过。`--limit/--start/--dry-run` 断点续跑；报告 `backfill_report.json`（remapped/created/dead/failed）。
- **失效识别**：GONE_HINTS/页面打不开 → 照常建 `source_product` 行但 `source_status=0`、不建 SKU 行，进 dead 报告清单（这些当下就有超卖风险）。
- **风控节奏**：3-10s/个（`--delay`），连续采集异常冷却 25min（`--cooldown 1500`）；启动守卫 = 9222 在线 + 归类v2/品牌/规格匹配不在跑；`run_stock_refresh.sh` 也反守卫本脚本（P1 夜跑期间 03:00 分级刷新自动 skip）。
- **夜间分段 launcher**：`.superpowers/sdd/2026-10-18-source-stock-monitor/run_backfill_nights.sh`——每晚 22:30（等 22:00 alimama 结束）起跑、每夜 timeout 20000s 硬停 05:00 前、避开周六凌晨（collect_full 退役前同窗撞 9222）、建档完成（待建档=0）自退；日志 `backfill_nights.log`。
- 报告 `created` 计数含绑定不重建；3 对重复档旧壳 6791/6030/6028 带活跃绑定未清理（双采风险已因 URL 结构性排除，留 owner 决定）。

### 分级刷新 detect_stock_change.py `--tiered`（2026-10-18，spec P2）

**三池口径**（`select_tiered` 纯函数）：
- **T1 每日池**：`min(status=1 的 source_sku.stock) < 100`（`--t1-threshold` 可调）**或从未刷新过**；
- **T2 常规池**：其余存活货源，`(id + day_of_year) % 7 == 0` 无状态轮转，每天 1/7；
- **T3 失效池**：`source_status=0`，**仅周一复查**，复活（拿到 SKU 数据）自动翻回 1 并销案；生死落库只升级 NULL/0→1，**不覆盖人工标记**。

- tiered 默认节奏与 `--pool` 系不同：`--max-per-run 600`、`--delay 5`（pool 系 60/10s）；受单轮上限的顺延不丢弃（deferred）。
- **硬停钟 `--stop-hour 5`**：05:00 前硬停把 9222 让给 05:30 ISV 同步；语义=**起跑时刻必须早于 stop_hour**（03:00+stop 5 满足，跨午夜组合不成立）；硬停 break 的商品不进 checked（有日志兜底）；tiered 下 `--stale-days` 静默忽略。
- 调度：LaunchAgent `com.spzx.stock-refresh` **每日 03:00** → `run_stock_refresh.sh`（守卫：9222 在线、归类v2/品牌/规格匹配/建档/上一轮刷新不在跑，skip 写 `cron_skipped` + failed 台账）。
- ⚠️ **gone→0 与周一 T3 复活路径未实跑**（单测覆盖纯函数），首次真实失效事件时盯日志。

### ISV 同步核验 isv_sync_verify.py（2026-10-18，spec P4）

**目的**：证明「1688 没货 → 淘宝被推成 0」真的发生（report 只记页数不算证据）。每轮 `isv_stock_sync.py` 成功后由 `run_stock_sync.sh` 自动接跑（`--cap 50`）：本地 0 库存且存活的绑定商品（超 cap 时 `ORDER BY RAND()` 随机抽，防无序 LIMIT 尾部永久盲区）+ 对照随机 10 个纯非零（**对照池排除混合库存商品**——探针实证混库行在「已关联货源」视图搜不到，会沉淀成假 verdict=3）。逐个开行级「同步记录」弹窗解析入库；`--dry-run` 只定位不点弹窗。

- **verdict 口径**（`stock_sync_check` 表，DDL `spzx-manager/src/main/resources/sql/stock_sync_check.sql`）：**1=成功同步为0**（record_text 含「同步为 N」且无失败字样）、2=无同步记录、3=失败/异常；解析纯函数 `parse_sync_record`。verdict 2/3 → `sync_alert` 按天去重。
- **探针结论（2026-10-18 门禁通过）**：ISV **会把 0 库存推成淘宝 0**——商品 1023052654615 的 10-17 同步记录 42 处「同步为0」逐 SKU=本地库存、Σ=165 吻合（证据=抽屉 innerText 存档 `.superpowers/sdd/2026-10-18-source-stock-monitor/task-11-drawer-text-*.txt`；9222 红线下不截图）。D1「商品失效人工下架」维持不变。
- 实测：`--cap 3` 真跑 3/3 verdict=1（零库存目标全部核验成功）。
- 坑：抽屉是 `.ant-drawer.product-sync-record-drawer`（**非 modal**）、空态竞态就绪判据、入口=行内联「同步记录」（无需下拉）、关闭=`.ant-drawer-close`。
