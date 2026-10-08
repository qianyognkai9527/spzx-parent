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
- 店铺中分类：`#sell-field-shopcat` 展开扁平 8 节点树，勾 `.next-tree-node` 内 `.next-checkbox-wrapper`，清空已有勾选后勾目标；校验 `#sell-field-shopcat .next-tag` 文本。
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
