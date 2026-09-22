# 消费分组（对账管理）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对账管理新增「消费分组」：账单记录页勾选订单加入命名分组（多对多），统计说明页展示分组卡片（总额/笔数/时间跨度）并支持明细/编辑/删除。

**Architecture:** 完全仿照已交付的标签模块（ExpenseTag/ExpenseOrderTag）：2 张新表 + 实体 + Mapper(@Select 聚合) + Service(ServiceImpl) + Controller，前端复用 api/expense.js 与两个既有页面的插入式改造。分组不参与既有统计口径。

**Tech Stack:** Spring Boot 3.3.5 + MyBatis-Plus 3.5.9（spzx-parent，GitHub）；Vue 3 + Element Plus + Vite（spzx-admin，Gitee）；MySQL db_spzx。

## Global Constraints

- spec: `docs/superpowers/specs/2026-09-22-expense-group-design.md`（spzx-parent）
- mvn 不在 PATH：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`
- 改 spzx-model 后必须 `mvn install -pl spzx-model -DskipTests -q` 再编 spzx-manager
- **禁止 `mvn test`**（拉起 Spring 上下文）；验证 = 编译 + 8501 curl 实测 + MySQL 直查
- 后端代码无注释（遵循代码库现状：仅个别类级中文 javadoc，方法不加注释）；Controller 返回 `Result.build(...)`，参数错误 `Result.build(null, 204, msg)`
- MySQL：`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e '...'`
- token：从 redis 拿（`/opt/homebrew/bin/redis-cli --scan --pattern 'user:login:*'`，value 即 token，头名 `token:`）；8501 不在线先重启（见 Task 7）
- 前端：system node v14 不可用，必须 `source ~/.nvm/nvmrc && nvm use 23`（或 `nvm use 23`）；提交触发 husky pre-commit lint，也需 node 23
- 前端 Prettier：单引号、无分号、printWidth 80；`<style lang="scss" scoped>`
- spzx-parent 是 git 仓库可提交；**spzx-admin 也是 git 仓库**（Gitee）；两仓都只 commit 不 push
- 测试数据纪律：**不得删除/修改已导入的 1908 条支付宝订单**；级联删除测试用手工录入订单（source=2）做

---

### Task 1: DB 迁移 — expense_group 两表

**Files:**
- Modify: `spzx-manager/src/main/resources/sql/expense_init.sql`（文件末尾追加）

**Interfaces:**
- Produces: `expense_group`、`expense_group_order` 表（复合主键 `(group_id, order_id)`，与 `expense_order_tag` 同构）

- [ ] **Step 1: 在 expense_init.sql 末尾追加**

```sql

-- ============ 消费分组（2026-09-22）============
-- 设计文档: docs/superpowers/specs/2026-09-22-expense-group-design.md

CREATE TABLE IF NOT EXISTS expense_group (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  group_name VARCHAR(50) NOT NULL COMMENT '分组名',
  remark VARCHAR(200) COMMENT '备注',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '消费分组';

CREATE TABLE IF NOT EXISTS expense_group_order (
  group_id BIGINT NOT NULL,
  order_id BIGINT NOT NULL,
  PRIMARY KEY (group_id, order_id),
  KEY idx_egorder_order (order_id)
) COMMENT '分组-订单关联（多对多，复合主键天然幂等）';
```

- [ ] **Step 2: 对 db_spzx 执行整个文件（幂等）**

Run: `/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx < spzx-manager/src/main/resources/sql/expense_init.sql && /usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e 'SHOW CREATE TABLE expense_group\G SHOW CREATE TABLE expense_group_order\G'`
Expected: 两表 DDL 输出，无报错；既有表/标签/菜单数据不变

- [ ] **Step 3: Commit**

```bash
git add spzx-manager/src/main/resources/sql/expense_init.sql
git commit -m "feat(expense): 消费分组建表 SQL"
```

---

### Task 2: 实体与 VO（spzx-model）

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/expense/ExpenseGroup.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/expense/ExpenseGroupOrder.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/expense/ExpenseGroupVo.java`

**Interfaces:**
- Consumes: 无（新文件）
- Produces: `ExpenseGroup`(id/groupName/remark/createTime/updateTime)、`ExpenseGroupOrder`(groupId/orderId)、`ExpenseGroupVo`(id/groupName/remark/totalCount/totalAmount/minDate/maxDate/createTime)

- [ ] **Step 1: 写三个文件**

`ExpenseGroup.java`：
```java
package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("expense_group")
public class ExpenseGroup extends Model<ExpenseGroup> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("group_name")
    private String groupName;

    @TableField("remark")
    private String remark;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
```

`ExpenseGroupOrder.java`（镜像 ExpenseOrderTag，无 id 字段）：
```java
package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("expense_group_order")
public class ExpenseGroupOrder {

    @TableField("group_id")
    private Long groupId;

    @TableField("order_id")
    private Long orderId;
}
```

`ExpenseGroupVo.java`：
```java
package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ExpenseGroupVo {

    private Long id;

    private String groupName;

    private String remark;

    private Integer totalCount;

    private BigDecimal totalAmount;

    private LocalDate minDate;

    private LocalDate maxDate;

    private LocalDateTime createTime;
}
```

- [ ] **Step 2: 编译安装 spzx-model**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && mvn install -pl spzx-model -DskipTests -q`
Expected: BUILD SUCCESS（静默）

---

### Task 3: Mapper（聚合查询）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/ExpenseGroupMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/ExpenseGroupOrderMapper.java`

**Interfaces:**
- Consumes: Task 2 实体/VO
- Produces: `ExpenseGroupMapper.listWithStats()` 返回 `List<ExpenseGroupVo>`；`ExpenseGroupOrderMapper` 为 BaseMapper（复杂操作全走 wrapper，不需要 XML）

- [ ] **Step 1: 写两个 Mapper**

`ExpenseGroupMapper.java`：
```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroup;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ExpenseGroupMapper extends BaseMapper<ExpenseGroup> {

    @Select("SELECT g.id, g.group_name, g.remark, g.create_time, " +
            "COUNT(go.order_id) AS totalCount, COALESCE(SUM(o.amount), 0) AS totalAmount, " +
            "MIN(o.expense_date) AS minDate, MAX(o.expense_date) AS maxDate " +
            "FROM expense_group g " +
            "LEFT JOIN expense_group_order go ON go.group_id = g.id " +
            "LEFT JOIN expense_order o ON o.id = go.order_id " +
            "GROUP BY g.id, g.group_name, g.remark, g.create_time " +
            "ORDER BY g.id DESC")
    List<ExpenseGroupVo> listWithStats();
}
```

`ExpenseGroupOrderMapper.java`：
```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ExpenseGroupOrderMapper extends BaseMapper<ExpenseGroupOrder> {
}
```

- [ ] **Step 2: 编译 spzx-manager**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && mvn compile -pl spzx-manager -am -q`
Expected: BUILD SUCCESS；已知既有错误仅 3 个支付策略 SDK 兼容问题（AbstractWechatPayStrategy/PaypalOrderStrategy/StripeCardStrategy），出现它们不算失败——但 -am 全量编译下这三个类会报错。若如此改用 `mvn compile -pl spzx-manager -q -o`，或确认错误仅限那 3 个文件即可视为通过（与对账管理后端交付时相同）

---

### Task 4: ExpenseOrderService 改造（分页 by ids + 级联删关联）

**Files:**
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/service/expense/ExpenseOrderService.java`

**Interfaces:**
- Consumes: Task 2 的 `ExpenseGroupOrder`、Task 3 的 `ExpenseGroupOrderMapper`
- Produces: `public Page<ExpenseOrderVo> pageByIds(long pageNum, long pageSize, List<Long> ids)`（Task 5 调用）；`delete`/`batchDelete` 级联清理 `expense_group_order`

- [ ] **Step 1: 加 import 与 @Autowired**

import 区新增：
```java
import com.joker.spzx.manager.mapper.ExpenseGroupOrderMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
```
字段区（`expenseTagMapper` 之后）新增：
```java
    @Autowired
    private ExpenseGroupOrderMapper expenseGroupOrderMapper;
```

- [ ] **Step 2: page 方法之后新增 pageByIds**

```java
    /** 按订单 id 集合分页（分组明细用），排序与列表页一致 */
    public Page<ExpenseOrderVo> pageByIds(long pageNum, long pageSize, List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return new Page<>(pageNum, pageSize);
        }
        LambdaQueryWrapper<ExpenseOrder> qw = new LambdaQueryWrapper<ExpenseOrder>()
                .in(ExpenseOrder::getId, ids)
                .orderByDesc(ExpenseOrder::getExpenseDate)
                .orderByDesc(ExpenseOrder::getTxnTime)
                .orderByDesc(ExpenseOrder::getId);
        Page<ExpenseOrder> page = expenseOrderMapper.selectPage(new Page<>(pageNum, pageSize), qw);
        Page<ExpenseOrderVo> out = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        out.setRecords(assembleVos(page.getRecords()));
        return out;
    }
```

- [ ] **Step 3: delete/batchDelete 各补一行级联清理**

`delete(Long id)` 变为：
```java
    @Transactional
    public void delete(Long id) {
        expenseOrderMapper.deleteById(id);
        expenseOrderTagMapper.delete(new LambdaQueryWrapper<ExpenseOrderTag>()
                .eq(ExpenseOrderTag::getOrderId, id));
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getOrderId, id));
    }
```
`batchDelete(List<Long> ids)` 变为：
```java
    @Transactional
    public int batchDelete(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return 0;
        }
        int n = expenseOrderMapper.deleteByIds(ids);
        expenseOrderTagMapper.delete(new LambdaQueryWrapper<ExpenseOrderTag>()
                .in(ExpenseOrderTag::getOrderId, ids));
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .in(ExpenseGroupOrder::getOrderId, ids));
        return n;
    }
```

- [ ] **Step 4: 编译**（命令同 Task 3 Step 2，预期同其注意事项）

---

### Task 5: ExpenseGroupService

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/expense/ExpenseGroupService.java`

**Interfaces:**
- Consumes: `ExpenseGroupMapper.listWithStats()`、`ExpenseOrderService.pageByIds()`、`ExpenseOrderService extends ServiceImpl` 自带的 `getById/listByIds`
- Produces:
  - `List<ExpenseGroupVo> listWithStats()`
  - `Long create(String groupName, String remark, List<Long> orderIds)`（建组+可选加入，返回新组 id）
  - `void rename(Long id, String groupName, String remark)`
  - `void deleteGroup(Long id)`
  - `int addOrders(Long groupId, List<Long> orderIds)` 返回实际新增关联数
  - `void removeOrder(Long groupId, Long orderId)`
  - `Page<ExpenseOrderVo> pageOrders(long pageNum, long pageSize, Long groupId)`
  - `public static class GroupDto { public String groupName; public String remark; public List<Long> orderIds; }`

- [ ] **Step 1: 写文件**

```java
package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ExpenseGroupMapper;
import com.joker.spzx.manager.mapper.ExpenseGroupOrderMapper;
import com.joker.spzx.manager.mapper.ExpenseOrderMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroup;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

@Service
public class ExpenseGroupService extends ServiceImpl<ExpenseGroupMapper, ExpenseGroup> {

    @Autowired
    private ExpenseGroupMapper expenseGroupMapper;

    @Autowired
    private ExpenseGroupOrderMapper expenseGroupOrderMapper;

    @Autowired
    private ExpenseOrderMapper expenseOrderMapper;

    @Autowired
    private ExpenseOrderService expenseOrderService;

    public static class GroupDto {
        public String groupName;
        public String remark;
        public List<Long> orderIds;
    }

    public List<ExpenseGroupVo> listWithStats() {
        return expenseGroupMapper.listWithStats();
    }

    @Transactional
    public Long create(String groupName, String remark, List<Long> orderIds) {
        ExpenseGroup g = new ExpenseGroup();
        g.setGroupName(groupName.trim());
        g.setRemark(remark == null || remark.isBlank() ? null : remark.trim());
        expenseGroupMapper.insert(g);
        addOrders(g.getId(), orderIds);
        return g.getId();
    }

    @Transactional
    public void rename(Long id, String groupName, String remark) {
        ExpenseGroup row = expenseGroupMapper.selectById(id);
        if (row == null) {
            throw new IllegalArgumentException("分组不存在: " + id);
        }
        if (groupName != null && !groupName.isBlank()) {
            row.setGroupName(groupName.trim());
        }
        if (remark != null) {
            row.setRemark(remark.isBlank() ? null : remark.trim());
        }
        expenseGroupMapper.updateById(row);
    }

    @Transactional
    public void deleteGroup(Long id) {
        expenseGroupMapper.deleteById(id);
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getGroupId, id));
    }

    @Transactional
    public int addOrders(Long groupId, List<Long> orderIds) {
        List<Long> valid = validOrderIds(orderIds);
        int added = 0;
        for (Long oid : valid) {
            ExpenseGroupOrder link = new ExpenseGroupOrder();
            link.setGroupId(groupId);
            link.setOrderId(oid);
            try {
                expenseGroupOrderMapper.insert(link);
                added++;
            } catch (DuplicateKeyException e) {
                // 已在同组，幂等忽略
            }
        }
        return added;
    }

    @Transactional
    public void removeOrder(Long groupId, Long orderId) {
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getGroupId, groupId)
                .eq(ExpenseGroupOrder::getOrderId, orderId));
    }

    public Page<ExpenseOrderVo> pageOrders(long pageNum, long pageSize, Long groupId) {
        List<Long> ids = expenseGroupOrderMapper.selectList(new LambdaQueryWrapper<ExpenseGroupOrder>()
                        .eq(ExpenseGroupOrder::getGroupId, groupId)
                        .select(ExpenseGroupOrder::getOrderId))
                .stream().map(ExpenseGroupOrder::getOrderId).toList();
        return expenseOrderService.pageByIds(pageNum, pageSize, ids);
    }

    private List<Long> validOrderIds(List<Long> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            return new ArrayList<>();
        }
        List<Long> distinct = new ArrayList<>(new LinkedHashSet<>(orderIds.stream()
                .filter(java.util.Objects::nonNull).toList()));
        if (distinct.isEmpty()) {
            return distinct;
        }
        List<Long> exist = expenseOrderMapper.selectList(new LambdaQueryWrapper<ExpenseOrder>()
                        .in(ExpenseOrder::getId, distinct)
                        .select(ExpenseOrder::getId))
                .stream().map(ExpenseOrder::getId).toList();
        return exist;
    }
}
```

- [ ] **Step 2: 编译**（命令同 Task 3 Step 2）

---

### Task 6: ExpenseGroupController

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/ExpenseGroupController.java`

**Interfaces:**
- Consumes: Task 5 全部方法与 GroupDto
- Produces: REST API（前端 Task 9 依赖）：
  - `GET /admin/expense/group/all` → `Result<List<ExpenseGroupVo>>`
  - `POST /admin/expense/group` body GroupDto → `Result<Long>`（新组 id；orderIds 可选）
  - `PUT /admin/expense/group/{id}` body GroupDto → `Result<Void>`
  - `DELETE /admin/expense/group/{id}` → `Result<Void>`
  - `POST /admin/expense/group/{id}/orders` body `{"orderIds":[...]}` → `Result<Integer>`
  - `DELETE /admin/expense/group/{id}/orders/{orderId}` → `Result<Void>`
  - `GET /admin/expense/group/{id}/orders/{pageNum}/{pageSize}` → `Result<Page<ExpenseOrderVo>>`

- [ ] **Step 1: 写文件**

```java
package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.expense.ExpenseGroupService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/expense/group")
public class ExpenseGroupController {

    @Autowired
    private ExpenseGroupService expenseGroupService;

    @GetMapping("/all")
    public Result<List<ExpenseGroupVo>> all() {
        return Result.build(expenseGroupService.listWithStats());
    }

    @PostMapping
    public Result<Long> create(@RequestBody ExpenseGroupService.GroupDto dto) {
        if (dto == null || dto.groupName == null || dto.groupName.isBlank()) {
            return Result.build(null, 204, "分组名不能为空");
        }
        if (dto.groupName.trim().length() > 50) {
            return Result.build(null, 204, "分组名不能超过 50 字");
        }
        try {
            return Result.build(expenseGroupService.create(dto.groupName, dto.remark, dto.orderIds));
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody ExpenseGroupService.GroupDto dto) {
        if (dto == null) {
            return Result.build(null, 204, "参数不能为空");
        }
        if (dto.groupName != null && dto.groupName.trim().length() > 50) {
            return Result.build(null, 204, "分组名不能超过 50 字");
        }
        try {
            expenseGroupService.rename(id, dto.groupName, dto.remark);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        try {
            expenseGroupService.deleteGroup(id);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PostMapping("/{id}/orders")
    public Result<Integer> addOrders(@PathVariable Long id, @RequestBody Map<String, List<Long>> body) {
        List<Long> ids = body == null ? null : body.get("orderIds");
        return Result.build(expenseGroupService.addOrders(id, ids));
    }

    @DeleteMapping("/{id}/orders/{orderId}")
    public Result<Void> removeOrder(@PathVariable Long id, @PathVariable Long orderId) {
        expenseGroupService.removeOrder(id, orderId);
        return Result.build(null);
    }

    @GetMapping("/{id}/orders/{pageNum}/{pageSize}")
    public Result<Page<ExpenseOrderVo>> orders(@PathVariable Long id,
                                               @PathVariable long pageNum,
                                               @PathVariable long pageSize) {
        return Result.build(expenseGroupService.pageOrders(pageNum, pageSize, id));
    }
}
```

- [ ] **Step 2: 编译 + 打包**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH" && mvn package -pl spzx-manager -am -DskipTests -q`
Expected: BUILD SUCCESS（同样只允许 3 个已知支付策略错误）；产物 `spzx-manager/target/spzx-manager.jar`

---

### Task 7: 重启 8501 + 后端 e2e 实测

**Files:** 无代码改动（验证任务）

**Interfaces:**
- Consumes: Task 1-6 全部；db_spzx；token
- Produces: 实测通过的 API；测试残留 = 1 个名为「SMOKE测试组」的组（Task 7 末尾自删）

- [ ] **Step 1: 重启 8501**

```bash
lsof -ti:8501 | xargs kill 2>/dev/null; sleep 2
cd /Users/qyk9527/ideaProject/spzx-parent && nohup java -jar spzx-manager/target/spzx-manager.jar > /tmp/spzx-manager-expense.log 2>&1 &
sleep 25 && curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8501/admin/expense/group/all -H 'token: BAD'
```
Expected: 最后输出 401 或 208（服务起来了、鉴权拦截生效即算 OK）

- [ ] **Step 2: 取 token**

Run: `/opt/homebrew/bin/redis-cli --scan --pattern 'user:login:*' | head -1 | xargs /opt/homebrew/bin/redis-cli get`
Expected: 32 位 hex token，记为 `$TOKEN`

- [ ] **Step 3: 建组+批量加入（用手工录入订单）**

先造一笔手工订单再建组：
```bash
curl -s -X POST http://127.0.0.1:8501/admin/expense/order -H "token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"expenseDate":"2026-09-22","amount":66.5,"channel":"其他","title":"SMOKE冒烟A"}'
curl -s -X POST http://127.0.0.1:8501/admin/expense/order -H "token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"expenseDate":"2026-09-22","amount":33.5,"channel":"其他","title":"SMOKE冒烟B"}'
```
（返回里没有 id——用 DB 查：`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "SELECT id FROM expense_order WHERE title LIKE 'SMOKE%' ORDER BY id"` 记为 `$OID1 $OID2`）

```bash
curl -s -X POST http://127.0.0.1:8501/admin/expense/group -H "token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"groupName":"SMOKE测试组","remark":"冒烟","orderIds":['$OID1','$OID2']}'
```
Expected: `{"code":200,...data=<新id>}`，记为 `$GID`

- [ ] **Step 4: 校验聚合/幂等/多组/明细**

```bash
curl -s "http://127.0.0.1:8501/admin/expense/group/all" -H "token: $TOKEN"
curl -s -X POST http://127.0.0.1:8501/admin/expense/group/$GID/orders -H "token: $TOKEN" -H 'Content-Type: application/json' -d '{"orderIds":['$OID1']}'
curl -s "http://127.0.0.1:8501/admin/expense/group/$GID/orders/1/10" -H "token: $TOKEN"
```
Expected 依次：列表含 `SMOKE测试组` 且 `totalCount=2, totalAmount=100.0`；重复加入返回 `data:0`（幂等）；明细分页 total=2 且含 tagNames 字段结构

- [ ] **Step 5: 改名 / 移出 / 级联**

```bash
curl -s -X PUT http://127.0.0.1:8501/admin/expense/group/$GID -H "token: $TOKEN" -H 'Content-Type: application/json' -d '{"groupName":"SMOKE改名组"}'
curl -s -X DELETE http://127.0.0.1:8501/admin/expense/group/$GID/orders/$OID1 -H "token: $TOKEN"
curl -s -X DELETE http://127.0.0.1:8501/admin/expense/order/$OID1 -H "token: $TOKEN"
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "SELECT COUNT(*) FROM expense_group_order WHERE order_id=$OID1"
```
Expected: 前三个 `code:200`；最后输出 `0`（订单删除级联清关联）

- [ ] **Step 6: 清理测试组 + 删另一笔 SMOKE 订单**

```bash
curl -s -X DELETE http://127.0.0.1:8501/admin/expense/group/$GID -H "token: $TOKEN"
curl -s -X DELETE http://127.0.0.1:8501/admin/expense/order/$OID2 -H "token: $TOKEN"
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "SELECT (SELECT COUNT(*) FROM expense_group),(SELECT COUNT(*) FROM expense_group_order),(SELECT COUNT(*) FROM expense_order WHERE title LIKE 'SMOKE%')"
```
Expected: `0 0 0`

- [ ] **Step 7: Commit 后端**

```bash
git add spzx-model/src/main/java/com/joker/spzx/model/entity/expense/ExpenseGroup.java \
        spzx-model/src/main/java/com/joker/spzx/model/entity/expense/ExpenseGroupOrder.java \
        spzx-model/src/main/java/com/joker/spzx/model/vo/expense/ExpenseGroupVo.java \
        spzx-manager/src/main/java/com/joker/spzx/manager/mapper/ExpenseGroupMapper.java \
        spzx-manager/src/main/java/com/joker/spzx/manager/mapper/ExpenseGroupOrderMapper.java \
        spzx-manager/src/main/java/com/joker/spzx/manager/service/expense/ExpenseGroupService.java \
        spzx-manager/src/main/java/com/joker/spzx/manager/service/expense/ExpenseOrderService.java \
        spzx-manager/src/main/java/com/joker/spzx/manager/controller/ExpenseGroupController.java
git commit -m "feat(expense): 消费分组后端（多对多+聚合统计+级联清理）"
```

---

### Task 8: 前端 API + 账单记录页「加入分组」

**Files:**
- Modify: `spzx-admin/src/api/expense.js`（文件末尾追加）
- Modify: `spzx-admin/src/views/expense/order/index.vue`

**Interfaces:**
- Consumes: Task 6 的 7 个接口
- Produces: API 函数 `GetExpenseGroupAll/CreateExpenseGroup/UpdateExpenseGroup/DeleteExpenseGroup/AddExpenseGroupOrders/RemoveExpenseGroupOrder/GetExpenseGroupOrders`；账单页勾选 → 加入分组弹窗

- [ ] **Step 1: api/expense.js 末尾追加**

```js
// ============ 分组 ============
export const GetExpenseGroupAll = () => {
  return request({
    url: `${api_name}/group/all`,
    method: 'get',
  })
}

export const CreateExpenseGroup = data => {
  return request({
    url: `${api_name}/group`,
    method: 'post',
    data,
  })
}

export const UpdateExpenseGroup = (id, data) => {
  return request({
    url: `${api_name}/group/${id}`,
    method: 'put',
    data,
  })
}

export const DeleteExpenseGroup = id => {
  return request({
    url: `${api_name}/group/${id}`,
    method: 'delete',
  })
}

export const AddExpenseGroupOrders = (id, orderIds) => {
  return request({
    url: `${api_name}/group/${id}/orders`,
    method: 'post',
    data: { orderIds },
  })
}

export const RemoveExpenseGroupOrder = (id, orderId) => {
  return request({
    url: `${api_name}/group/${id}/orders/${orderId}`,
    method: 'delete',
  })
}

export const GetExpenseGroupOrders = (id, pageNum, pageSize) => {
  return request({
    url: `${api_name}/group/${id}/orders/${pageNum}/${pageSize}`,
    method: 'get',
  })
}
```

- [ ] **Step 2: order/index.vue — op-bar 加按钮**

`op-bar` 里「手工录入」按钮之后、「批量删除」之前插入：
```html
        <el-button
          type="warning"
          :disabled="!selection.length"
          @click="openAddGroup"
        >
          加入分组{{ selection.length ? `（${selection.length}）` : '' }}
        </el-button>
```

- [ ] **Step 3: order/index.vue — el-table 加 ref**

`<el-table :data="rows" ...>` 加 `ref="tableRef"`（clearSelection 用）。

- [ ] **Step 4: order/index.vue — 导入弹窗 dialog 之后追加「加入分组」dialog**

```html
    <el-dialog v-model="groupDlg" title="加入分组" width="480px">
      <el-form label-width="90px">
        <el-form-item label="加入方式">
          <el-radio-group v-model="groupForm.mode">
            <el-radio value="existing">加入已有分组</el-radio>
            <el-radio value="new">新建分组</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="groupForm.mode === 'existing'" label="选择分组">
          <el-select
            v-model="groupForm.groupId"
            placeholder="选择分组"
            style="width: 100%"
          >
            <el-option
              v-for="g in groups"
              :key="g.id"
              :label="`${g.groupName}（${g.totalCount || 0} 笔）`"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="分组名" required>
          <el-input
            v-model="groupForm.groupName"
            maxlength="50"
            placeholder="如：九月置装"
          />
        </el-form-item>
      </el-form>
      <div class="form-tip">
        将把选中的 {{ selection.length }} 笔账单加入该分组；同一账单可属于多个分组，重复加入自动忽略
      </div>
      <template #footer>
        <el-button @click="groupDlg = false">取消</el-button>
        <el-button type="primary" :loading="groupSaving" @click="doAddGroup">
          确定
        </el-button>
      </template>
    </el-dialog>
```

- [ ] **Step 5: order/index.vue — script 改造**

import 区追加：`CreateExpenseGroup, GetExpenseGroupAll, AddExpenseGroupOrders`；删除无关不改。

el-table ref + 状态/方法（放在「============ 删除 ============」小节之前）：
```js
// ============ 加入分组 ============
const tableRef = ref(null)
const groupDlg = ref(false)
const groupSaving = ref(false)
const groups = ref([])
const groupForm = reactive({ mode: 'existing', groupId: null, groupName: '' })

const openAddGroup = async () => {
  groupForm.mode = 'existing'
  groupForm.groupId = null
  groupForm.groupName = ''
  const res = await GetExpenseGroupAll()
  if (res.code === 200) groups.value = res.data || []
  if (!groups.value.length) groupForm.mode = 'new'
  groupDlg.value = true
}

const doAddGroup = async () => {
  const ids = selection.value.map(r => r.id)
  if (!ids.length) return
  if (groupForm.mode === 'new') {
    if (!groupForm.groupName.trim()) {
      ElMessage.warning('请填写分组名')
      return
    }
  } else if (!groupForm.groupId) {
    ElMessage.warning('请选择分组')
    return
  }
  groupSaving.value = true
  try {
    const res =
      groupForm.mode === 'new'
        ? await CreateExpenseGroup({
            groupName: groupForm.groupName.trim(),
            orderIds: ids,
          })
        : await AddExpenseGroupOrders(groupForm.groupId, ids)
    if (res.code !== 200) {
      ElMessage.error(res.message || '加入失败')
      return
    }
    ElMessage.success('已加入分组')
    groupDlg.value = false
    tableRef.value?.clearSelection()
  } finally {
    groupSaving.value = false
  }
}
```

- [ ] **Step 6: Commit 前端（第一部分）**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin
git add src/api/expense.js src/views/expense/order/index.vue
git commit -m "feat(expense): 账单记录页勾选订单加入分组"
```
（husky 需要 node 23：`nvm use 23` 后再提交）

---

### Task 9: 统计说明页「消费分组」区块

**Files:**
- Modify: `spzx-admin/src/views/expense/stats/index.vue`

**Interfaces:**
- Consumes: Task 8 的 API 函数
- Produces: 分组卡片区块 + 明细弹窗 + 编辑弹窗

- [ ] **Step 1: template — 月度趋势卡片与「口径与使用说明」卡片之间插入区块**

```html
    <el-card shadow="never" class="block-card">
      <template #header>
        <div class="monthly-header">
          <span>消费分组</span>
          <span class="group-tip">
            在「账单记录」勾选订单 → 「加入分组」，把一批相关消费打包对比
          </span>
        </div>
      </template>
      <div v-if="!groups.length" class="group-empty">
        暂无分组：去「账单记录」页勾选几笔订单（如一次置装的衣服+洗衣液），创建你的第一个分组
      </div>
      <el-row v-else :gutter="12">
        <el-col
          v-for="g in groups"
          :key="g.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="6"
          class="group-col"
        >
          <div class="group-card" @click="openGroupDetail(g)">
            <div class="group-name-row">
              <span class="group-name" :title="g.remark || g.groupName">
                {{ g.groupName }}
              </span>
              <span class="group-ops" @click.stop>
                <el-button link type="primary" @click="openGroupEdit(g)">
                  编辑
                </el-button>
                <el-button link type="danger" @click="removeGroup(g)">
                  删除
                </el-button>
              </span>
            </div>
            <div class="group-amount">
              {{ g.totalCount ? fmtMoney(g.totalAmount) : '--' }}
            </div>
            <div class="group-sub">
              {{ g.totalCount || 0 }} 笔
              <span v-if="g.totalCount && g.minDate">
                · {{ g.minDate }} ~ {{ g.maxDate }}
              </span>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
```

- [ ] **Step 2: template — 文件末尾 `</div>`（app-container 结束）前追加两个弹窗**

明细弹窗：
```html
    <el-dialog
      v-model="detailDlg"
      :title="`分组明细：${detailGroup?.groupName || ''}`"
      width="760px"
    >
      <el-table :data="detailRows" v-loading="detailLoading" border size="small">
        <el-table-column prop="expenseDate" label="消费日期" width="105" />
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }">
            <span class="amount">¥{{ Number(row.amount).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="channel" label="渠道" width="90" />
        <el-table-column
          prop="title"
          label="说明"
          min-width="200"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            {{ row.title || row.counterparty || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="removeDetail(row)">
              移出
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="detailPage"
        :page-size="detailSize"
        :total="detailTotal"
        layout="total, prev, pager, next"
        class="pager"
        @current-change="loadGroupDetail"
      />
    </el-dialog>

    <el-dialog v-model="editDlg" title="编辑分组" width="440px">
      <el-form label-width="80px">
        <el-form-item label="分组名" required>
          <el-input v-model="editForm.groupName" maxlength="50" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDlg = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveGroupEdit">
          保存
        </el-button>
      </template>
    </el-dialog>
```

- [ ] **Step 3: script 改造**

import 区改为：
```js
import { ElMessage, ElMessageBox } from 'element-plus'
```
（`ElMessage` 原本就有，补 `ElMessageBox`；其余 import 不动，再从 api 追加：）
```js
import {
  GetExpenseGroupAll,
  UpdateExpenseGroup,
  DeleteExpenseGroup,
  RemoveExpenseGroupOrder,
  GetExpenseGroupOrders,
} from '@/api/expense'
```

script 末尾（onMounted 之前）加分组逻辑：
```js
// ============ 消费分组 ============
const groups = ref([])

const loadGroups = async () => {
  const res = await GetExpenseGroupAll()
  if (res.code === 200) groups.value = res.data || []
}

const detailDlg = ref(false)
const detailGroup = ref(null)
const detailRows = ref([])
const detailTotal = ref(0)
const detailPage = ref(1)
const detailSize = 10
const detailLoading = ref(false)

const openGroupDetail = g => {
  detailGroup.value = g
  detailPage.value = 1
  detailDlg.value = true
  loadGroupDetail()
}

const loadGroupDetail = async () => {
  if (!detailGroup.value) return
  detailLoading.value = true
  try {
    const res = await GetExpenseGroupOrders(
      detailGroup.value.id,
      detailPage.value,
      detailSize
    )
    if (res.code === 200) {
      detailRows.value = res.data.records || []
      detailTotal.value = Number(res.data.total) || 0
    }
  } finally {
    detailLoading.value = false
  }
}

const removeDetail = async row => {
  try {
    await ElMessageBox.confirm(
      `把「${row.title || row.counterparty || '该笔账单'}」移出分组？账单本身不受影响`,
      '移出分组',
      { type: 'warning' }
    )
  } catch {
    return
  }
  const res = await RemoveExpenseGroupOrder(detailGroup.value.id, row.id)
  if (res.code !== 200) {
    ElMessage.error(res.message || '移出失败')
    return
  }
  ElMessage.success('已移出')
  loadGroupDetail()
  loadGroups()
}

const editDlg = ref(false)
const editSaving = ref(false)
const editingGroup = ref(null)
const editForm = reactive({ groupName: '', remark: '' })

const openGroupEdit = g => {
  editingGroup.value = g
  editForm.groupName = g.groupName
  editForm.remark = g.remark || ''
  editDlg.value = true
}

const saveGroupEdit = async () => {
  if (!editForm.groupName.trim()) {
    ElMessage.warning('请填写分组名')
    return
  }
  editSaving.value = true
  try {
    const res = await UpdateExpenseGroup(editingGroup.value.id, {
      groupName: editForm.groupName.trim(),
      remark: editForm.remark,
    })
    if (res.code !== 200) {
      ElMessage.error(res.message || '保存失败')
      return
    }
    ElMessage.success('已保存')
    editDlg.value = false
    loadGroups()
  } finally {
    editSaving.value = false
  }
}

const removeGroup = async g => {
  try {
    await ElMessageBox.confirm(
      `确认删除分组「${g.groupName}」（${g.totalCount || 0} 笔）？仅解除关联，不影响订单本身`,
      '删除分组',
      { type: 'warning' }
    )
  } catch {
    return
  }
  const res = await DeleteExpenseGroup(g.id)
  if (res.code !== 200) {
    ElMessage.error(res.message || '删除失败')
    return
  }
  ElMessage.success('已删除分组')
  loadGroups()
}
```

`onMounted` 里 `loadRangeData()` 之后补 `loadGroups()`；`reactive` 需在顶部 vue import 里加入（现在是 `import { ref, computed, onMounted, onUnmounted } from 'vue'` → 加 `reactive`）。

- [ ] **Step 4: style 末尾追加**

```scss
.group-tip {
  font-size: 12px;
  color: #999;
}

.group-empty {
  color: #909399;
  font-size: 13px;
  padding: 24px 0;
  text-align: center;
}

.group-col {
  margin-bottom: 12px;
}

.group-card {
  height: 100%;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 14px;
  background: #fafbfc;
  cursor: pointer;
  transition: border-color 0.2s;

  &:hover {
    border-color: #409eff;
  }

  .group-name-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;

    .group-name {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .group-ops {
      flex-shrink: 0;
    }
  }

  .group-amount {
    font-size: 20px;
    font-weight: 700;
    color: #303133;
    margin-top: 6px;
  }

  .group-sub {
    font-size: 12px;
    color: #a8abb2;
    margin-top: 4px;
  }
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.amount {
  font-weight: 600;
}
```

- [ ] **Step 5: lint + build**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin && nvm use 23 && npm run lint
cd /Users/qyk9527/webstormProject/spzx-admin && nvm use 23 && npm run build
```
Expected: lint 无 error；build 成功（仅既有 chunk-size warning）

---

### Task 10: 前端提交 + 人工验收指引

**Files:** 无新改动

- [ ] **Step 1: Commit**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin
nvm use 23
git add src/views/expense/stats/index.vue
git commit -m "feat(expense): 统计说明页消费分组区块（卡片+明细+编辑）"
```

- [ ] **Step 2: 向用户报告验收路径**

报告内容：刷新 3001 → 账单记录页勾选几笔 → 「加入分组」→ 统计说明页看「消费分组」卡片；提示用户点卡片看明细、可编辑/删除。附后端 e2e 已验证的口径（重复加入幂等、删组不影响订单、删订单级联清关联）。
