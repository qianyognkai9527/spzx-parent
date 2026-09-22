# 对账管理实施计划（expense_*）

- 日期：2026-09-22
- 设计文档：`docs/superpowers/specs/2026-09-22-expense-tracking-design.md`（含实测样例解析规则与统计口径，**以设计文档为准**）
- 后端与 DB：本会话主线程实现；前端：并行子代理，完成后统一 build 验证

## 步骤

1. **DB**（`spzx-manager/src/main/resources/sql/expense_init.sql`，直接执行到 db_spzx）
   - 3 张表 expense_order / expense_tag / expense_order_tag（DDL 见设计 §2）
   - 预置标签 8 个（幂等）
   - sys_menu：父「对账管理」component=expense + 子 expenseOrder/expenseTag/expenseStats（显式 id = MAX(id)+1 起，WHERE NOT EXISTS 幂等）+ sys_role_menu role 9
2. **后端**（包：`com.joker.spzx.model.entity.expense` / `com.joker.spzx.manager`）
   - 实体：ExpenseOrder / ExpenseTag / ExpenseOrderTag（照 KwProvider 风格）
   - VO：ExpenseOrderVo（含 tagIds/tagNames）、ImportResultVo、SummaryVo（spzx-model vo/expense）
   - 解析器：`service/expense/AlipayBillCsvParser`（纯 Java 无 Spring；gb18030→utf8 回退；定位表头行；只收支出；交易关闭跳过；strip \t；quote 感知 CSV 分隔）
   - Mapper：ExpenseOrderMapper（BaseMapper + @Select 统计）、ExpenseTagMapper、ExpenseOrderTagMapper
   - Service：ExpenseOrderService（分页组装标签/新增/编辑/删除/导入去重）、ExpenseTagService、ExpenseStatsService（summary/daily/byTag/byChannel/monthly）
   - Controller：ExpenseOrderController（/admin/expense/order/*）、ExpenseTagController（/admin/expense/tag/*）、ExpenseStatsController（/admin/expense/stats/*）
3. **后端验证**：`mvn install -pl spzx-model -DskipTests -q` → `mvn compile -pl spzx-manager -am`（注意 AGENTS.md 已知策略类编译错误是否仍在）；解析器 JUnit 单测用真实样例 `/Users/qyk9527/我的/支付宝交易明细(20260122-20260920).csv` 断言：2805 行、支出 1932、关闭 13、交易号唯一
4. **前端**（spzx-admin，子代理）：api/expense.js、router/modules/expense.js + index.js 注册、views/expense/{order,tag,stats}/index.vue、home/index.vue 近30天消费柱状图；`npm run build` 验证
5. **端到端**：重启 8501 → Redis 取 token → curl 导入真实 CSV 两次（第二次全 skippedDuplicate）→ summary/daily 与 SQL 直查核对
6. 提交代码（spzx-parent GitHub；spzx-admin Gitee，仅提交本次相关文件）

## 验收清单

- [ ] 3 表 + 8 预置标签 + 4 菜单行 + role 9 授权就位
- [ ] 解析器单测通过（真实样例）
- [ ] 导入样例：imported≈1919 / skippedNonExpense 873 / skippedClosed 13 / 重复导入全 skip
- [ ] stats/daily、summary 数值与 SQL 直查一致
- [ ] npm build 通过；3001 页面三菜可见（用户目验）
