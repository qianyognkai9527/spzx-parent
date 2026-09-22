# 对账管理设计（expense_*）

- 日期：2026-09-22
- 状态：设计完成，待实现
- 范围：spzx-parent（后端）+ spzx-admin（前端）+ db_spzx（3 张新表）
- 参考：照 kw_*（AI选词）模块既有模式实现

## 1. 背景与目标

个人消费对账：记录每日花费，来源两类——

1. 支付宝账单 CSV 导入（网页版导出，周期性不定期下载导入）
2. 手工录入非支付宝渠道的消费（美团/京东/拼多多/淘宝/抖音商城/其他）

支持多标签（一笔消费可打多个标签，标签可在页面增删改），首页展示近 30 天消费柱状图，另设统计说明页展示汇总数据与口径。

**假设**：个人使用，不做按用户隔离（与 kw 模块一致）。

## 2. 数据模型（db_spzx）

```sql
CREATE TABLE IF NOT EXISTS expense_order (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  expense_date DATE NOT NULL COMMENT '消费日期（按日统计分组键）',
  txn_time DATETIME COMMENT '交易时间（导入=交易创建时间；手工可空）',
  amount DECIMAL(12,2) NOT NULL COMMENT '支出金额，正数',
  channel VARCHAR(32) NOT NULL DEFAULT '其他' COMMENT '渠道：支付宝/淘宝/京东/拼多多/抖音商城/美团/其他',
  source TINYINT NOT NULL COMMENT '来源：1支付宝导入 2手工录入',
  title VARCHAR(255) COMMENT '商品说明/内容',
  counterparty VARCHAR(128) COMMENT '交易对方（导入用）',
  alipay_trade_no VARCHAR(64) DEFAULT NULL COMMENT '支付宝交易订单号（去重键，手工为NULL）',
  remark VARCHAR(255),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_trade_no (alipay_trade_no)
) COMMENT '消费账单记录';

CREATE TABLE IF NOT EXISTS expense_tag (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(32) NOT NULL COMMENT '标签名',
  color VARCHAR(16) COMMENT '前端标签颜色（el-tag type 色）',
  sort_value INT DEFAULT 0,
  status TINYINT DEFAULT 1 COMMENT '1启用 0停用（停用不删，历史关联保留）',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name)
) COMMENT '消费标签';

CREATE TABLE IF NOT EXISTS expense_order_tag (
  order_id BIGINT NOT NULL,
  tag_id BIGINT NOT NULL,
  PRIMARY KEY (order_id, tag_id)
) COMMENT '账单-标签关联';
```

预置标签（幂等播种）：购物/饮食/交通/日用/娱乐/通讯/医疗/其他。

要点：
- `uk_trade_no` 对手工录入（NULL）不生效，MySQL 唯一索引允许多个 NULL。
- DDL 汇总在 `spzx-manager/src/main/resources/sql/expense_init.sql`（含预置标签、菜单播种，全部幂等 `WHERE NOT EXISTS`）。

## 3. 支付宝账单导入（按实测样例钉死）

实测样例：`我的/支付宝交易明细(20260122-20260920).csv`（2805 行记录）。

文件结构（实测）：
- **编码 gb18030**（GBK 兼容），无 BOM，混合 CRLF/LF
- 文件头：`----` 分隔行 + 导出信息块（姓名/账户/起止时间/共 N 笔记录 + 收支汇总）+ 空行 + 特别提示块
- **表头行**：`交易时间,交易分类,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,`（尾部多一个空列）
- 数据行内字段含尾部 `\t`（交易订单号等），需 strip
- 文件尾无汇总行，以数据行结束

解析规则：
1. 读 bytes，尝试 gb18030 解码（失败再试 utf-8）
2. 逐行找 `col0=='交易时间'` 的行定位表头，按列名取索引（不依赖固定列序）
3. 只导入 `收/支 == '支出'` 的行；`收入`/`不计收支` → skippedNonExpense
4. `交易状态 == '交易关闭'` 的支出行跳过 → skippedClosed（交易未完成，非真实花费；样例中 13 笔）
5. 金额全部为正（实测 0 笔负数），直接入库
6. `交易订单号` strip 后作 `alipay_trade_no`，DB 唯一键兜底去重 → skippedDuplicate
7. `expense_date` = 交易时间日期部分；channel='支付宝'，source=1；title=商品说明；counterparty=交易分类（比对方账号更有用，实测如 餐饮美食/日用百货/转账红包）
8. 导入接口为幂等：同一文件重复导入安全

预期（样例实测核对）：total 2805 → imported ≈1919，skippedNonExpense 873（收入421+不计收支452），skippedClosed 13。

## 4. 后端（spzx-parent，URL 前缀 `/admin/expense`）

实体在 `spzx-model/entity/expense/`；Controller/Service/Mapper 在 spzx-manager（Service 放 `service/expense/`）；返回 `Result<T>`；认证走既有 LoginAuthInterceptor，不加 @PreAuthorize。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/order/import`（multipart） | 导入支付宝 CSV，返回 `{total, imported, skippedDuplicate, skippedNonExpense, skippedClosed, errors[]}` |
| GET | `/order/list/{pageNum}/{pageSize}` | 分页；筛选：expenseDateBegin/End、channel、tagId、keyword（title/counterparty/remark） |
| POST | `/order` | 手工新增（channel/amount/expenseDate/tagIds/remark/txn_time 可空） |
| PUT | `/order/{id}` | 编辑（含 tagIds 全量覆盖） |
| DELETE | `/order/{id}` | 单删 |
| POST | `/order/batchDelete` | 批删 |
| GET | `/tag/all` | 全量启用标签（下拉数据源） |
| POST/PUT/DELETE | `/tag`、`/tag/{id}` | 标签 CRUD（删除校验：有订单引用时拒绝或提示，默认拒绝） |
| GET | `/stats/daily?days=30` | `[{date, amount}]`，首页+统计页柱状图 |
| GET | `/stats/summary?days=30` | `{today, last7, last30, monthTotal}` 卡片 |
| GET | `/stats/byTag?days=30` / `/stats/byChannel?days=30` / `/stats/monthly?year=2026` | 统计图数据 |

CSV 解析器独立类 `AlipayBillCsvParser`（manager 模块 service/expense 下），便于单测。

## 5. 前端（spzx-admin，新菜单组「对账管理」）

- `src/router/modules/expense.js`：父组 path `/expense`（name `expense`，Layout，icon），3 个子页（lazy import）：
  - `views/expense/order/index.vue` — name `expenseOrder`，path `/expenseOrder`：筛选栏（日期范围/渠道/标签/关键词）+ 表格（金额、渠道、标签 el-tag 多个、来源、日期、说明）+ 分页 + 「导入支付宝账单」上传对话框（导入后展示各项计数明细）+「手工录入」对话框
  - `views/expense/tag/index.vue` — name `expenseTag`，path `/expenseTag`：标签 CRUD（名称/颜色/排序/启停）
  - `views/expense/stats/index.vue` — name `expenseStats`，path `/expenseStats`：4 张汇总卡片 + 按标签饼图 + 按渠道柱图 + 月度趋势折线（echarts）+ 「口径与使用说明」文字块
- `src/api/expense.js`：照 `api/kw.js` 模式（request util、`/admin/expense` 前缀、分页走 URL path）
- 首页 `views/home/index.vue`：新增「近 30 天消费」柱状图卡片，复用现有 echarts 初始化/resize 模式，数据调 `stats/daily?days=30`
- 菜单播种（expense_init.sql）：顶级目录行 `对账管理`（parent_id=0，component=`expense`，照 `mall`/`order` 模式）+ 3 个子菜单行（component=路由 name）+ `sys_role_menu` 授 role 9；全部幂等

## 6. 统计口径（统计页「说明」文案）

1. 只统计支出：导入时自动剔除收入/不计收支行；「交易关闭」的支出行视为未完成交易，不计入
2. 支付宝导入按交易订单号唯一去重，同一文件重复导入安全
3. 手工录入仅记录非支付宝渠道消费，与支付宝账单互补不重叠
4. 标签多对多：按标签统计时一笔多标签消费同时计入多个标签，故各标签之和可能大于总支出
5. 渠道口径：支付宝账单里的消费实际发生在各平台，统一记为「支付宝」渠道；手工录入的才标注具体渠道

## 7. 错误处理

- 导入：文件空/找不到表头行 → 明确报错（code 204 风格）；单行金额非法等 → 计入 errors[]（含行号+原因）继续处理其余行
- 标签删除被引用 → 拒绝并提示
- 手工录入金额 ≤0 / 缺日期 → 前端表单校验 + 后端校验

## 8. 测试要点

- `AlipayBillCsvParser` 单测：用样例文件结构断言（表头定位、strip \t、收/支过滤、交易关闭过滤、去重）
- 导入实测：样例文件导入两次，第二次全部 skippedDuplicate
- 统计核对：`stats/daily` 某日合计 vs SQL `SUM(amount)` 直查一致
- 菜单可见性：role 9 登录 3001 能看到三个新菜单；未授权角色看不到

## 9. 不做的事（YAGNI）

- 不做预算/提醒、不做多账本、不做用户隔离
- 不做支付宝账单自动拉取（手动下载手动导入）
- 不做退款冲抵统计（收入行整体剔除，口径见 §6）
- 不做导入记录的逐条修改限制（导入记录同样可编辑/删除）
