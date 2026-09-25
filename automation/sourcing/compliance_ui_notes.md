# 合规控件结构发现 (自动生成 2026-09-25 10:51, 人工核对补充 11:10)

> 只读 dump，全程未提交表单、未保存草稿。样本 = 5 个已 failed 商品（页面自带失败错误态）。
> 首轮 dump 用 `probe_compliance_ui.py`（brief 原始假设）；attrs 假设落空后按「label 文本 + sell-field 容器」换思路重探 4 轮（临时 probe 脚本未入库），结论已验证。

## 原始 dump（首轮，DUMP_JS 按 brief 假设）

## 1072552474230
```json
{
 "qtf": {
  "tag": "TD",
  "cls": "sell-sku-cell sell-sku-cell-title",
  "inZone": true
 },
 "matBtn": {
  "tag": "SPAN",
  "cls": "next-btn-helper"
 },
 "attrs": []
}
```

## 1058428800598
```json
{
 "qtf": {
  "tag": "TD",
  "cls": "sell-sku-cell sell-sku-cell-title",
  "inZone": true
 },
 "matBtn": null,
 "attrs": []
}
```

## 888970440898
```json
{
 "qtf": {
  "tag": "TD",
  "cls": "sell-sku-cell sell-sku-cell-title",
  "inZone": true
 },
 "matBtn": {
  "tag": "SPAN",
  "cls": "next-btn-helper"
 },
 "attrs": []
}
```

## 1071720043442
```json
{
 "qtf": {
  "tag": "TD",
  "cls": "sell-sku-cell sell-sku-cell-title",
  "inZone": true
 },
 "matBtn": {
  "tag": "SPAN",
  "cls": "next-btn-helper"
 },
 "attrs": []
}
```

## 1078910949614
```json
{
 "qtf": {
  "tag": "TD",
  "cls": "sell-sku-cell sell-sku-cell-title",
  "inZone": true
 },
 "matBtn": null,
 "attrs": []
}
```

⚠️ **首轮假设落空**：页面**不存在** `.next-form-item` / `.next-form-item-label`（attrs 5 样本全空）；matBtn 命中的 `SPAN.next-btn-helper` 只是按钮内 label span（不可直接当点击目标）。真实结构如下。

---

# 结论与选择器修正

## 1. 「去填写」可点击元素（SKU）

首轮 finder 命中的 `TD.sell-sku-cell-title` 是**单元格**（文本恰好等于"去填写"），真实可点击按钮在其内部：

```html
<td class="sell-sku-cell sell-sku-cell-title">
  <div class="item-wrapper"><div class="cell-inner-new">
    <div class="sku-component-sku-detail">
      <button type="button" class="next-btn next-medium next-btn-primary next-btn-text">
        <span class="next-btn-helper">去填写</span>
      </button>
```

- **修正后选择器**：`#sell-field-sku .sell-sku-cell-title button.next-btn`（fallback `#sell-field-sku button.next-btn-text`）
- 点击后打开**右侧 drawer**：`.next-drawer.next-drawer-right.sku-component-sku-detail-drawer`
  - header：`.sku-detail-title`（含 `.sku-detail-sku-id`，如 "SKU ID: 6123847373020"）+ `.next-drawer-close` 关闭
  - body：`.drawer-inner` → 顶部错误提示 `.next-message.next-message-error.global-message`（如"白色 - M：厚薄不能为空。"）+ `.block-wrapper` 属性块
  - drawer 内字段壳与主页面同构（`sell-component-info-wrapper-wrap` + `.sell-component-info-wrapper-label`）
- 5 样本全部有该按钮（qtf=True ×5）

## 2. 「添加材质成分」按钮

```html
<button type="button" class="next-btn next-medium next-btn-normal add-new">
  <span class="next-btn-helper">添加材质成分</span>
</button>
```

- **修正后选择器**：`#sell-field-p-149422948 button.add-new`（面料材质成分字段内；里料材质成分 `#sell-field-p-151386995` 同构）
- 通用 fallback：按文本找 `button.add-new`（勿用 span.next-btn-helper）
- **点击行为 = 字段内联展开（非浮层）**：无 dialog/drawer，DOM 直接在字段内展开：

```
.sell-catProp-item-material
  .material-content
    .content
      .sell-o-images.ocr-image-upload-wrap        ← 上传吊牌（可选）
      .material-item                              ← 每种材质一行
        span.next-select.next-select-trigger.next-select-single...（placeholder 请选择材质）
        span.sell-o-number.count-number.has-unit  ← 选中材质后才出现
          input[placeholder="输入含量"]           ← 含量数字输入, 单位 %
        a.delete                                  ← 删除该行
      button.next-btn.add-new                     ← 再加一行
    .text（规则：最多 7 种材质；填含量则总和必须 100%）
```

- 下拉选项 popup：`.next-overlay-wrapper.opened > .next-select-popup-wrap.sell-o-select-popup-overlay.sell-catProp-item-material-select-options`，选项 = `.options-item[title=材质名]`（实测含"聚酯纤维""其他材质""再生纤维素纤维"等；`.options-search input` fill 可过滤，实测搜"聚酯"→3 项）
- **类目差异**：材质成分专用 UI 只在服装类目（家居服/连衣裙/秋冬款=面料材质成分 p-149422948 + 里料 p-151386995；连衣裙里该字段 id 同为 p-149422948 但 label 是"材质成分"且 REQ）。**长裤无此字段**——其"材质成分"是普通文本输入（p-574077422，next-input，0/100）；**美甲(other) 也没有**——只有"材质"单选下拉 p-657638212。Task 3 必须按类目分支。

## 3. 属性区目标字段控件类型（5 样本实测）

字段容器统一结构（每字段）：

- 容器：`#sell-field-p-<propId>`，class 含 `sell-component-info-wrapper-wrap sell-component-item-prop-item`
- label：`.sell-component-info-wrapper-label`（必填星号 `*` 在文本内；「重要」角标是单独节点）
- 控件根：`#struct-p-<propId>`（`data-id="struct-catProp-p-<propId>"`）
- **propId 随类目变化，不能硬编码 → 必须按 label 文本定位**（定位法：全文找 `.sell-component-info-wrapper-label` 文本匹配 → 上溯至 `[id^="sell-field-p-"]` 容器）

四目标字段（type 按 trigger class 判定：`next-select-single`=单选 / `next-select-multiple`=多选 / `next-select-tag`=tag 可搜索）：

| 字段 | 家居服 1072552474230 | 长裤 1058428800598 | 连衣裙 888970440898 | 秋冬款 1071720043442 | other(美甲) 1078910949614 |
|------|------|------|------|------|------|
| 上市年份季节 | p-8560225 single 有值 | p-122216347 single 有值 | p-122216347 single **空(页ERR)** | p-8560225 single 有值 | p-8560225 single（label 显示为「上市时间」） |
| 是否商场同款 | p-587225836 single 空 | **无此字段** | **无此字段** | p-653084398 single **空(页ERR)** | **无此字段** |
| 功能 | p-587223957 **multiple** 空 | p-124108695 single 空 | p-556419065 single 有值(亲肤透气) | p-654351012 **multiple** **空(页ERR)** | p-657533549 **multiple** 空 |
| 适用场景 | p-122216515 single 有值(运动家居) | **无此字段** | p-557004586 **tag** 有值(citywalk) | p-654373903 **multiple** **空(页ERR)** | p-657638215 **multiple** 有值(日常, 已选择1/8) |

（「页ERR」= 页面自带上次提交失败错误态，字段文本含"必填项…不能为空"，即 Task 4 待填字段）

**下拉控件统一结构（Task 4 填写法依据）**：

- trigger：`span.next-select.next-select-trigger` 内 `input[role="combobox"]`（readonly）；已选值 = `em[title=值]` 或 `.next-tag`；多选已选计数 = `.next-select-tag-compact`"已选择 X/Y 项"
- 点击 trigger → popup：`.next-overlay-wrapper.opened > .next-select-popup-wrap.sell-o-select-popup-overlay`
  - 搜索框 `.options-search input`（fill 可过滤选项）
  - 选项列表 `.options-content`（**虚拟滚动**，固定高度 560px；找不全时必须先搜索再点）
  - 选项元素：`.options-item[title=选项名] > .sell-o-info > .info-content`（功能字段选项实测：保暖/凉感/助眠/可外穿/吸湿/导汗/抗菌/抗过敏/智能温控/轻盈裸感/远红外/透气/速干…）
- trigger class 前缀 `next-inactive` → 打开后变 `next-active`（可用于断言 popup 状态）

## 4. 与 Task 2-4 代码 SELECTORS 假设的差异清单

1. **`.next-form-item` / `.next-form-item-label` 不存在** → 属性字段定位改为 `[id^="sell-field-p-"]` 容器 + `.sell-component-info-wrapper-label` 文本匹配，再取内部 `#struct-p-<id>` 控件根。
2. **「去填写」点击目标**：brief 文本 finder 会命中 `TD.sell-sku-cell-title`（不可点击样式正确性未知）→ 改用 `#sell-field-sku .sell-sku-cell-title button.next-btn`。
3. **「添加材质成分」**：文本 finder 命中 `SPAN.next-btn-helper`（子元素）→ 改用 `button.add-new`；且点击是**内联展开**，Task 3 不要等 dialog/drawer 出现，直接查 `#sell-field-p-149422948 .material-item`。
4. **含量输入在选中材质后才出现**：`input[placeholder="输入含量"]`；选材质前不存在。含量为可选项（不填则按重要程度排序），填则总和=100%。
5. **属性下拉选项不是 `.next-menu-item`** → 是 `.options-item[title=...]`，在 `.next-select-popup-wrap.sell-o-select-popup-overlay` 内；列表虚拟滚动，选项可能不在 DOM，需 `.options-search input` 搜索过滤。
6. **功能/适用场景的单/多选随类目变**（见第 3 节表）：Task 4 不能写死 single/multiple，按 trigger class 现场判定；`next-select-tag`（连衣裙适用场景）走 trigger 内直接输入+tag 确认路径。
7. **是否商场同款仅部分类目存在**（家居服/秋冬款），长裤/连衣裙/美甲无 → 定位失败时跳过不报错。
8. **材质成分 UI 仅服装类目有**（见第 2 节）：长裤=文本输入 p-574077422、美甲=材质下拉 p-657638212，Task 3 按类目分支。
9. propId 跨类目不映射同字段（功能在 5 样本中 id 全不同），一切以 label 文本为准；上市年份季节例外——服装类恒为 p-8560225 或 p-122216347 两个 id（按类目二选一），美甲类 label 变「上市时间」。

## 附：5 样本 p-* 字段清单（propId | REQ | 页ERR | label | 当前值摘要）

### 1072552474230（家居服/睡裙，29 字段）
- p-149422948 面料材质成分(有添加按钮) / p-151386995 里料材质成分
- p-8560225 REQ 上市年份季节=2022年夏季 / p-122216345 REQ 适用季节=秋季 / p-20608 家居服风格=性感 / p-122216588 服装款式细节=镂空 / p-122216515 适用场景=运动家居
- p-587223957 功能=请选择(multiple) / p-20663 REQ 领型=一字领 / **p-587227907 REQ 页ERR 面料=空** / p-122216349 REQ 裙长=短裙 / p-122216348 REQ 袖长=无袖
- p-587204900 安全等级 / p-587205197 版型 / p-413423496 工艺=印花(1/16) / p-587227709 面料弹力 / p-8366967 主面料克重=200g及以下 / p-587205200 裙型 / p-587227417 柔软度 / p-587225836 是否商场同款 / p-122216608 适用对象=青年 / p-587223966 透气性 / p-20603 图案=纯色 / p-587227418 腰型 / p-31611 衣门襟=无扣
- p-20000 REQ 品牌=瑰若 / p-21299 产地=中国 / p-13021751 款号 / p-100029786 是否带胸垫=不带胸垫

### 1058428800598（长裤，20 字段）
- p-20551 REQ 面料=牛仔布 / p-122216347 REQ 上市年份季节=2026年夏季 / p-128132720 REQ 适用人群 / p-20677 REQ 腰型 / p-413972959 REQ 版型 / p-36228475 REQ 弹力等级
- p-573667073 安全等级 / p-574077422 材质成分(文本0/100) / p-21299 产地 / p-344943689 吊牌价 / p-34272 工艺=做旧 / p-124108695 功能=请选择(single) / p-13021751 货号 / p-2047670 裤门襟 / p-574077425 款式细节 / p-20000 品牌 / p-122216345 适用季节 / p-574078009 图案 / p-573740662 系列 / p-619198215 材质软硬

### 888970440898（连衣裙，30 字段）
- p-149422948 REQ 材质成分(添加按钮) / p-20608 REQ 风格=法式 / p-20551 REQ 面料=聚酯纤维 / p-18551851 REQ 裙型=公主裙 / **p-122216347 REQ 页ERR 上市年份季节=空**
- p-557004586 REQ 适用场景=citywalk(tag) / p-557023937 REQ 适用人群=女士 / p-122216348 REQ 袖长 / p-20000 品牌=十三行
- p-557004581 版型=修身型 / p-21299 产地=中国 / p-557004582 穿着方式=套头 / p-557023934 弹性指数=微弹 / p-344943689 吊牌价 / p-556419065 功能=亲肤透气(single) / p-122216507 厚薄=薄款 / p-13021751 货号 / p-122276315 款式=吊带连衣裙 / p-122216588 款式细节=蕾丝拼接 / p-148886213 廓形=A型 / p-414028058 里料=蚕丝 / p-20663 领型=V领 / p-413423496 面料工艺=拼接 / p-413503587 柔软指数=适中 / p-20017 适用年龄=25-29周岁 / p-557023935 系列 / p-2917380 袖型=无袖 / p-20677 腰型=中高腰 / p-31611 衣门襟=拉链 / p-10142888 组合形式=单件

### 1071720043442（秋冬款，30 字段）
- p-151386995 里料材质成分 / p-149422948 面料材质成分
- **p-654351012 REQ 页ERR 功能=空(multiple)** / p-20000 REQ 品牌=无品牌 / p-8560225 REQ 上市年份季节=2025年春季 / **p-654373903 REQ 页ERR 适用场景=空(multiple)** / p-122216345 REQ 适用季节=四季通用 / p-20608 家居服风格 / p-122216608 适用对象 / p-20603 图案 / p-24477 REQ 适用性别=女 / p-653829786 安全等级 / p-654351015 版型 / p-654365008 单件重量 / p-344943689 REQ 吊牌价 / p-122216507 厚薄=常规 / p-13021751 款号 / p-653214692 裤长 / p-654365010 裤门襟 / p-122216588 服装款式细节 / p-654365012 领型 / p-216832544 主面料克重 / p-654365009 吸水性 / p-654373902 袖长 / p-653829788 腰型 / p-653214691 衣门襟 / p-122216349 长度 / p-653084399 款式 / p-20551 面料俗称 / **p-653084398 REQ 页ERR 是否商场同款=空**

### 1078910949614（other/美甲，32 字段）
- p-657638215 REQ 适用场景=日常(1/8 multiple) / p-164190454 产品类别 / p-34581 美甲产品分类 / p-1626691 REQ 包装种类 / p-21299 REQ 产地=中国大陆 / p-122276080 REQ 规格=片 / p-20000 REQ 品牌 / p-20000~1 REQ 型号 / p-140400482 REQ 是否为特殊用途化妆品=否 / p-251346001 保质期 / p-261129106 注册人备案人地址 / p-261225606 注册人备案人名称 / p-657638212 材质 / p-168946038 产品名称 / p-657533549 功能=请选择(multiple) / p-19368082 化妆品特性 / p-13021751 货号 / p-100832593 甲型 / p-147956252 净含量 / p-657532191 批准文号 / p-8560225 上市时间(single) / p-151454497 生产厂家地址 / p-151486361 生产厂家名称 / p-234181213 生产企业生产许可证号 / p-3364156 适合肤质 / p-657533264 适用部位 / p-657533263 适用年龄 / p-657533553 适用人群 / p-261128416 责任企业地址 / p-261127820 责任企业名称 / p-16061820 执行标准号 / p-3545 制作工艺

## 附2：探查方法备注

- 全程 `connect_cdp(9222, keep_urls=["myseller.taobao.com","item.upload.taobao.com"])`，每样本 `ctx.new_page()` 新 tab 用完即关，Escape 关面板；结束时 tab 数与开跑前一致（零泄漏）。
- 误判教训：`.next-menu` 扫描会命中页面吸顶导航（基础信息/销售信息/物流服务/图文描述），真下拉在 `.next-select-popup-wrap`；`wrapper_content_panel`/`panel_edit`（图文详情编辑器）是页面常驻大面板，勿当弹层处理。
- probe5 证实材质编辑为内联展开（字段 outerHTML 2495→3466 字节，浮层数不变）。

---

# Task 3 补记 (2026-09-25 下午, SKU 填充实测, 样本=长裤 1058428800598)

## 1. 「去填写」→ 右侧抽屉（每行一个，非批量面板）

点击行内「去填写」开 `.next-drawer.next-drawer-right.sku-component-sku-detail-drawer`：

- title：`.sku-detail-title` "详情 SKU ID: xxx"
- body `.drawer-inner`：顶部 `.next-message.next-message-error`（该行**全部**缺失字段，如 "黑灰色【高品质】 - L：是否加绒不能为空。 裤型不能为空。 裤长不能为空。"）+ 属性块（label `.sell-component-info-wrapper-label` + trigger `span.next-select`，字段**异步加载**，trigger 带 `sell-component-sku-asyn` class）
- 按钮在抽屉 body 底部（无 `.next-drawer-footer`）：确定 `button.confirm-button-first` + 取消 `button.confirm-button`
- ⚠️ **抽屉「确定」会被该行其他必填字段拦死**：长裤实测只填「是否加绒」点确定 → 抽屉不关，msg 停留在 "裤型不能为空。 裤长不能为空。"。→ 抽屉路径无法"只填已知字段"，**不可用作填充器通道**
- ⚠️ 「取消」会弹 `.next-dialog` 确认框（`.next-overlay-wrapper.opened` 内、带 backdrop 拦截一切后续点击），行为未验证，勿依赖
- 抽屉内选值**即时同步主表单态**（抽屉未关、主页面错误行已消失）

## 2. 真正的填充面 = SKU 表格内联下拉列（无任何确认）

- 表头：18 个 `DIV.sell-sku-table-header-common-new`（容器 `.sell-sku-thead.sell-sku-div-head`，**div 表格、无 thead/th**），文本=列名，**顺序与数据行 TD 一一对应**
- 数据行：`#sell-field-sku tr`（TBODY 内 `.sku-table-row`），TD id=`{行号}-skuParam_p-{propId}`（如 `0-skuParam_p-573740654`）；非属性列 id：`{行号}-skuPicture / -p-1627207 / -p-20518 / -skuPrice / -skuStock / -skuQuality / -skuPostCouponPrice / -skuOuterId / -skuBarcode / -sellPointCollection / -skuTitle / -skuStatus / -action`
- 缺失单元格 class 含 `has-error`（首个缺失另有 `focused`）
- **定位法（propId 不硬编码）**：表头文本 === 字段名 → 列号 → 首行该列 TD id 反解 propId → 逐行 `[id="{i}-skuParam_p-{propId}"] span.next-select` 点击 → 选项 `.next-overlay-wrapper.opened .options-item[title=值]`（与属性区下拉同构，选项少时无搜索框）→ 点选后 trigger 的 innerText 即已选值
- **选值即时写回表单态、无确认按钮**（表格单元格与价格输入同级，是主表单一部分）

## 3. 错误行来源（detect_gaps 的 SKU 信号）

`.sell-sku-table-wrapper-new` 内 `.msg-bar > .next-message.next-message-error.next-inline`，文本如 "黑灰色【高品质】 - L：是否加绒不能为空。"（首个/focused 缺失行）；该行填完后消失。

## 4. 长裤样本列身份 + 未知必填字段警告

- 是否加绒=p-573740654 / 裤型=p-122276315 / 厚薄=p-122216507（与属性区「厚薄」id 同源）/ 适用体型=p-574077433 / 裤长=p-122276111
- ⚠️ 抽屉报该行 **裤型/裤长 必填缺失**，但主页面错误行只报「是否加绒」——提交校验是否卡裤型/裤长未知，探路提交时观察（影响 design 里"长裤样本完整成功"预期）

## 5. 工程坑

- ⚠️ **抽屉/弹窗未关时 `page.close()` 会泄漏 tab**（实测漏 3 个 item.upload tab，keep_urls 含 item.upload 时启动清理不回收；已全部清理并补守卫 tab）。脚本收尾先 Escape 关浮层再关 page。
- 表头是 div 表格，`querySelectorAll('thead')`/`th` 全部落空（Task 1 首轮 `thead: null` 的真正原因）。
- 本节全部探查只读+单行选值，**未提交表单、未保存草稿**（页面关闭即弃）。

---

# Task 4 补记 (2026-09-25 下午, 属性级填充实测, 样本=连衣裙 888970440898 + 秋冬款 1071720043442)

## 1. 「面料」≠「材质成分」组合（brief 假设修正）

brief 把 面料/材质成分 合并走「添加材质成分」组合路径——**实测两者是独立字段**：

- **面料** = 普通属性单选下拉（长裤/连衣裙=p-20551，家居服=p-587227907），选项如 牛仔布/聚酯纤维，走通用下拉路径即可。
- **材质成分组合 UI 只属于「面料材质成分/材质成分」字段**（服装类 p-149422948）；`prop_value_for('材质成分')` 保持 `'材质:含量'` 格式，`prop_value_for('面料')` 返回普通下拉候选。

## 2. ⚠️ 深坑：选值已生效但校验读到 detach 节点 → 30s 假失败

`_set_next_select` 首版在**点击选项之后**才 `opt.get_attribute('title')`——单选点选项**弹层立即关闭、选项节点 detach**，locator 自动重解析等默认 30s 后抛 TimeoutError，被逐候选 except 吞掉 → 返回 None 报「候选值均未命中」，**但值实际已写入**（re-detect gap 已消失，消息却是失败，且早退跳过后续字段）。两样本均 33s/字段 假失败实锤。

- **修法**：选项 `title` **必须点击前取**；所有 locator 动作显式 `timeout=3000~8000`，`inner_text` 包 try/except；搜索框先 `is_visible()` 再 fill（`next-no-search` 的 trigger 弹层可能无/藏搜索框）。
- 教训：Playwright locator 默认 30s 超时在「点击后读弹层内元素」场景必踩，凡跨弹层生命周期读属性都要前置或加短超时。

## 3. 属性下拉交互实测（两样本 4 字段全通过）

- 定位：`.sell-component-info-wrapper-label` 文本（去 `*`/空白/重要/必填）**精确匹配** → `closest('[id^="sell-field-p-"]')`（排除 `.next-drawer` 内同构壳）；「上市年份季节」美甲类 label=「上市时间」按别名次序优先匹配。
- 单选（上市年份季节/是否商场同款）：点 trigger → `.next-overlay-wrapper.opened .next-select-popup-wrap` → 点 `.options-item[title=值]` → **弹层自动关**，trigger innerText 即写回值；上市年份季节弹层选项全量直出（2026年冬季/2026年秋季/2012年春季…），无需搜索。
- 多选（功能/适用场景，秋冬款 multiple）：点选项**弹层不自动关**，需 Escape；trigger 写回态 = 「已选择 X/Y 项」(compact) 或 tag 文本，两者都要认。
- 搜索框：是否商场同款弹层 `.options-search input` 存在且可见；fill 过滤后再点精确 title，匹配不到清空搜索回落首个可见选项（合规目标=非空）。
- 每字段填充前须重调 `clear_overlays`（React 重渲染复位隐藏，继承提示属实）。

## 4. 未覆盖/遗留

- **tag-select 路径仍未实测**：连衣裙适用场景(`next-select-tag`)有值(citywalk)未成 gap，本轮没遇到 tag gap；`_set_next_select` 对 tag 按单选弹层路径尝试，真遇到需现场 dump（继承提示的「再探一步」仍欠着）。
- **fill_extract_way 在两样本均返回 `(False,'CLICK_NO_EFFECT')`**（Task 2 函数，长裤样本曾 CHECKED）：两页面 extract 无 gap（detect 不报），点击后 checked 仍 falsy，疑因运费模板子状态不同；不影响本轮（AFTER 无 extract gap），Task 5 集成时若遇 extract gap 需注意此返回值。
- 验证值来源：功能=保暖、适用场景=居家 均为标题关键词命中（标题含 保暖/睡衣/家居服），非兜底回落。

## 5. 验证记录（12:24，未提交、页面关闭即弃，无风控）

```
888970440898: gaps BEFORE=[上市年份季节] → filled 上市年份季节=2026年秋季 → gaps AFTER=[]
1071720043442: gaps BEFORE=[是否商场同款,功能,适用场景] → filled 是否商场同款=否,功能=保暖,适用场景=居家 → gaps AFTER=[]
```
