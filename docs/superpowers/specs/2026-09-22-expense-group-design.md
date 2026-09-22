# 对账管理·消费分组 设计（2026-09-22）

## 背景与目标

对账管理已交付（见 `2026-09-22-expense-tracking-design.md`）。本次新增**消费分组**：把一批相关订单（如一次置装的「新衣服 + 洗衣粉 + 洗衣液」多笔消费）打包成命名分组，长期留档，用于对比「每批一共花了多少钱」。

## 用户决策

- **用途**：长期留档对比——统计页常驻分组卡片（总额/笔数/时间跨度），点开看明细
- **归属关系**：**多对多**，一笔订单可同时属于多个分组（同标签模式）
- **展示位置**：统计说明页新增「消费分组」区块，**不新增菜单**
- 0 元订单导入时已过滤（既有规则，本次不变）；分组不参与现有收支统计

## 数据模型（db_spzx，追加进 expense_init.sql，幂等）

```sql
CREATE TABLE IF NOT EXISTS expense_group (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  group_name VARCHAR(50) NOT NULL COMMENT '分组名',
  remark VARCHAR(200) NULL COMMENT '备注',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消费分组';

CREATE TABLE IF NOT EXISTS expense_group_order (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  group_id BIGINT NOT NULL,
  order_id BIGINT NOT NULL,
  UNIQUE KEY uk_group_order (group_id, order_id),
  KEY idx_egorder_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分组-订单关联';
```

- 逻辑外键，不做物理 FK；`uk_group_order` 保证重复加入幂等
- 删组 → 只删 `expense_group_order` 关联行，**不动订单**；删订单 → 级联删关联行（与 expense_order_tag 同处理）

## 后端（spzx-parent，完全仿照 ExpenseTag 模式）

- 实体：`ExpenseGroup`、`ExpenseGroupOrder`（spzx-model，`@TableName` + `extends Model<T>`，字段与表一一对应）
- `ExpenseGroupVo`（spzx-model）：分组字段 + `totalCount` / `totalAmount` / `minDate` / `maxDate`（LEFT JOIN 关联表+订单聚合，0 笔时金额/日期为 null）
- `ExpenseGroupMapper`（+XML：listWithStats / selectOrderPage）、`ExpenseGroupService`（ServiceImpl）、`ExpenseGroupController`

接口（鉴权走 /admin 全局拦截器，控制器不写鉴权，返回 `Result.build`）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/expense/group/all` | 全量分组列表（含统计字段，按 create_time desc） |
| POST | `/admin/expense/group` | 新建；groupName 必填非空、≤50 字，否则 204 报错 |
| PUT | `/admin/expense/group/{id}` | 重命名/改备注（传什么改什么） |
| DELETE | `/admin/expense/group/{id}` | 删组 + 清关联（二次确认由前端做） |
| POST | `/admin/expense/group/{id}/orders` | body `{orderIds:[]}`；过滤不存在的订单 id，幂等加入（唯一键冲突忽略） |
| DELETE | `/admin/expense/group/{id}/orders/{orderId}` | 单笔移出 |
| GET | `/admin/expense/group/{id}/orders?page=&limit=` | 组内订单分页（列同账单记录：日期/金额/渠道/标题/来源/备注） |

- 订单删除（`ExpenseOrderController` DELETE）处补删 `expense_group_order` where order_id=?

## 前端（spzx-admin，仿标签交互）

- `api/expense.js`：groupAll / groupCreate / groupUpdate / groupDelete / groupAddOrders / groupRemoveOrder / groupOrders
- **账单记录页**：表格加 `type=selection` 列；选中 >0 时工具栏出现「加入分组」按钮 → 弹窗二选一：下拉选已有组（显示「组名（N笔）」）或输入新组名现场创建并加入；成功后刷新列表并提示
- **统计说明页**：图表下方新增「消费分组」区块，卡片栅格：
  - 卡片内容：组名、总金额（大字）、笔数、时间跨度（最早~最晚日期）
  - 点卡片 → 明细弹窗：组内订单分页表格 + 单笔「移出」
  - 卡片操作：编辑（改名/备注）、删除（ElMessageBox 确认文案注明「仅解除关联，不影响订单本身」）
  - 空态：一句引导文案「在账单记录页勾选订单即可创建分组」

## 边界与规则

1. 分组**不参与** summary/daily/byTag/byChannel/monthly 统计与口径文案，互不影响
2. 多对多：同一订单可在多个组，各组合额独立直加（uk 防同组重复行，不会重复计费）
3. 删组不删订单；删订单级联清关联
4. 组金额 = 组内订单 amount 之和；空组显示 0 笔 / 金额 —（前端渲染「—」）
5. 组名不做全局唯一限制（标签允许同名先例）

## 验收清单

1. 账单记录勾选 3 笔 → 加入分组「九月置装」→ 统计页卡片显示 3 笔、总额=3 笔之和
2. 同一订单重复加入同一组：关联表不出现重复行
3. 同一订单加入两个组：两组各自统计含该订单
4. 明细弹窗单笔移出 → 卡片总额/笔数即时更新
5. 删组：关联行消失、订单仍在；删订单：关联行级联消失
6. `mvn compile`（spzx-model install → spzx-manager）通过；前端 `npm run build` 通过
