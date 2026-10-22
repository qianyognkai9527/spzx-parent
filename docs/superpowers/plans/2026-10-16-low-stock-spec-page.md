# 低库存规格页面实现计划（2026-10-16）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后台「运营管理」新增「低库存规格」只读页：1688 货源规格级低库存按货源分组展示 + 淘宝商品外跳，数据现算不物化。

**Architecture:** 三块——① `taobao_offer_map` 小映射表（淘宝 item ↔ 1688 offer ↔ source_product_id）由 `sku_match_report.json` 一次性导入、`isv_sku_match.py` 每轮 UPSERT 刷新；② 后端 `LowStockController` 现算三段式查询（分组分页 + 该页映射 + 该页低规格明细）；③ 前端 lowStock.vue 展开行展示，<10 红 / 10~19 橙。

**Tech Stack:** Spring Boot 3.3.5 + MyBatis-Plus 3.5.9（IPage 分页）/ Vue 3 + Element Plus 2.9.4 + Pinia / Python 3.9（automation/venv，pymysql + dbconf）

**Spec:** `docs/superpowers/specs/2026-10-16-low-stock-spec-page-design.md`

## Global Constraints

- **绝不 `git commit`**（本仓库硬规则，覆盖技能模板的 commit 步骤——每个任务以验证收尾，不落 commit）。
- Maven 不在 PATH：先 `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`。
- 改 `spzx-model`（新 VO）后必须 `mvn install -pl spzx-model -DskipTests -q` 再编译 manager。
- 单测必须 `-am`：`mvn test -pl spzx-manager -am -Dtest=XxxTest -Dsurefire.failIfNoSpecifiedTests=false`。
- MySQL CLI 一律 `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx`（客户端不支持行内 `\G`）。
- Python 一律 `automation/venv/bin/python`；DB 连接一律 `from dbconf import DB_CONFIG` + `pymysql.connect(**DB_CONFIG)`。
- 后端唯一入口 `spzx-manager`（端口 8501，profile dev）；`GlobalExceptionHandler` 已把 `ServiceException(400, msg)` 转成 `code 400 + 人话`。
- `sys_menu` 现有最大 id=78；新菜单 id=79，parent_id=38（运营管理），role_id=9（照推广日报 76/77/78 的配法）。
- `source_product` 无 `title` 列——标题列 `source_product_name`；URL 列 `source_product_url`（形如 `https://detail.1688.com/offer/{oid}.html`）。
- 前端仓库在 `/Users/qyk9527/webstormProject/spzx-admin`（spzx-parent 兄弟目录）；Element Plus 2.9.4 的 `el-radio-button` 用 `:value` prop（不是 `label`）。
- 期望量级（2026-10-16 实测）：threshold=20 时 186 个货源 / 1358 个低库存规格；`source_sku` 共 14824 行 / 838 货源。
- 数据事实：`sku_match_report.json` 4203 items / 3815 distinct offers；`source_product` 5847 行中 2367 行 URL 含 offer id。

---

### Task 1: DB——`taobao_offer_map` 建表 + 菜单种子

**Files:**
- Create: `spzx-manager/src/main/resources/sql/taobao_offer_map.sql`（SQL 文件落此处，与 `promo_plan.sql` 同目录）

**Interfaces:**
- Produces: 表 `taobao_offer_map(taobao_item_id UNIQUE, offer_id, source_product_id, update_time)`；菜单行 sys_menu id=79 + sys_role_menu(9,79)。Task 2/4/5 依赖。

- [ ] **Step 1: 写 SQL 文件**

```sql
-- 淘宝商品 ↔ 1688 货源映射。来源 automation/sourcing/sku_match_report.json
-- （import_offer_map.py 一次性导入；isv_sku_match.py 每轮结束 UPSERT 刷新）。
-- 一个淘宝商品只挂一个货源（uk_item）；一个货源对应多个淘宝商品是正常态。
CREATE TABLE IF NOT EXISTS taobao_offer_map (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  taobao_item_id BIGINT NOT NULL COMMENT '淘宝商品 itemId',
  offer_id BIGINT NOT NULL COMMENT '1688 货源 offerId',
  source_product_id BIGINT NULL COMMENT 'source_product.id，导入时解析 source_product_url 回填；解析不到留 NULL',
  update_time DATETIME NULL,
  UNIQUE KEY uk_item (taobao_item_id),
  KEY idx_offer (offer_id),
  KEY idx_sp (source_product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 菜单：运营管理(id=38) 下「低库存规格」，sort 22（推广计划 21 之后、AI选词 60 之前）
INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 79, 38, '低库存规格', 'lowStock', 22, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE id = 79);

-- 角色授权照推广日报（76/77/78 都是 role_id=9）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, 79 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM sys_role_menu WHERE role_id = 9 AND menu_id = 79);
```

- [ ] **Step 2: 执行 SQL**

Run: `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx < /Users/qyk9527/ideaProject/spzx-parent/spzx-manager/src/main/resources/sql/taobao_offer_map.sql`
Expected: 无报错（幂等，可重跑）。

- [ ] **Step 3: 验证**

Run: `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SHOW COLUMNS FROM taobao_offer_map; SELECT id,title,component,sort_value,status FROM sys_menu WHERE id=79; SELECT * FROM sys_role_menu WHERE menu_id=79;"`
Expected: 4 个业务列（taobao_item_id/offer_id/source_product_id/update_time）；sys_menu 一行 `低库存规格/lowStock/22/1`；sys_role_menu 一行 `(9,79)`。

---

### Task 2: `import_offer_map.py`——映射导入脚本 + 单测 + 首次导入

**Files:**
- Create: `automation/sourcing/import_offer_map.py`
- Test: `automation/sourcing/test_import_offer_map.py`

**Interfaces:**
- Consumes: `automation/sourcing/sku_match_report.json`（top key `items`，元素含 `item_id`/`offer_id` 字符串）；`source_product.source_product_url`。
- Produces: `refresh_table(items, conn=None) -> int`（UPSERT 行数）——Task 3 的 isv_sku_match.py 会 `from import_offer_map import refresh_table`。表 taobao_offer_map 被 Task 4 的 mapper 查询。

- [ ] **Step 1: 写测试（先红）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""import_offer_map 纯函数单测（无网络无 DB，仓库惯例：python 直跑）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_offer_map import parse_offer_id  # noqa: E402


def test_parse_offer_id():
    assert parse_offer_id("https://detail.1688.com/offer/980287802829.html") == 980287802829
    assert parse_offer_id("https://detail.1688.com/offer/123.html?spm=x") == 123
    assert parse_offer_id("http://detail.1688.com/offer/456.html") == 456
    assert parse_offer_id("") is None
    assert parse_offer_id(None) is None
    assert parse_offer_id("https://tb.com/x") is None


def test_parse_offer_id_real_mixed_urls():
    # 库里也存过非 offer 形态的 1688 URL，不能误解析
    assert parse_offer_id("https://www.1688.com/") is None
    assert parse_offer_id("https://detail.1688.com/offer/0.html") == 0


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("all ok")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python test_import_offer_map.py`
Expected: `ModuleNotFoundError`/ImportError（import_offer_map.py 还不存在）。

- [ ] **Step 3: 写脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sku_match_report.json -> DB taobao_offer_map（淘宝 item ↔ 1688 offer ↔ source_product）。

只做映射，不碰 source_sku/source_product 数据本身。offer_id -> source_product_id 在
导入时解析 source_product_url 回填（5847 行里 2367 行是 offer 形态 URL），查询侧免拆 URL。
"""
import json
import os
import re
import sys

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbconf import DB_CONFIG  # noqa: E402

OFFER_RE = re.compile(r"detail\.1688\.com/offer/(\d+)\.html")
DEFAULT_REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sku_match_report.json")


def parse_offer_id(url):
    """从 source_product_url 提取 offer id；非 offer 形态/空返回 None。"""
    if not url:
        return None
    m = OFFER_RE.search(url)
    return int(m.group(1)) if m else None


def refresh_table(items, conn=None):
    """全量 UPSERT taobao_offer_map。items 是 report['items'] 列表（item_id/offer_id 字符串）。

    返回 upsert 行数。传入 conn 时不接管连接生命周期（isv_sku_match 尾部复用连接场景不传也行，
    统一让本函数自管，简单可靠）。
    """
    own = conn is None
    if own:
        conn = pymysql.connect(**DB_CONFIG, charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, source_product_url FROM source_product "
                "WHERE source_product_url LIKE '%detail.1688.com/offer/%' AND is_deleted = 0")
            sp_by_offer = {}
            for sp_id, url in cur.fetchall():
                oid = parse_offer_id(url)
                if oid is not None:
                    sp_by_offer[oid] = sp_id
            rows = []
            for it in items:
                item_id = str(it.get("item_id") or "").strip()
                offer_id = str(it.get("offer_id") or "").strip()
                if not item_id.isdigit() or not offer_id.isdigit():
                    continue
                rows.append((int(item_id), int(offer_id), sp_by_offer.get(int(offer_id))))
            if not rows:
                return 0
            cur.executemany(
                "INSERT INTO taobao_offer_map (taobao_item_id, offer_id, source_product_id, update_time) "
                "VALUES (%s, %s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE offer_id = VALUES(offer_id), "
                "source_product_id = VALUES(source_product_id), update_time = NOW()",
                rows)
            return len(rows)
    finally:
        if own:
            conn.close()


def main():
    report = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPORT
    with open(report, encoding="utf-8") as f:
        items = json.load(f)["items"]
    n = refresh_table(items)
    print(f"taobao_offer_map upsert {n} rows（report: {report}）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python test_import_offer_map.py`
Expected: `all ok`

- [ ] **Step 5: 首次导入并验证行数**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python import_offer_map.py`
Then: `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SELECT COUNT(*) AS rows_total, COUNT(DISTINCT offer_id) AS offers, COUNT(source_product_id) AS with_sp FROM taobao_offer_map;"`
Expected: rows_total=4203，offers≈3815，with_sp≈2367 上下（report 里的 offer 都该出现在 source_product URL 集，数量接近但不必相等——以「rows_total=4203、offers 在 3800~3830」为过）。

---

### Task 3: `isv_sku_match.py` 尾部接映射刷新

**Files:**
- Modify: `automation/sourcing/isv_sku_match.py`（`run()` 内 `write_csv` 之后、`return 0` 之前，约 617-619 行）

**Interfaces:**
- Consumes: Task 2 的 `refresh_table(items)`；本脚本内 `rep`（dict，含 `items` 列表）与 `log()`。

- [ ] **Step 1: 修改 run() 收尾**

把：

```python
        n = write_csv(args.csv, rep)
        log(f"完成：本轮处理 {processed} 个，人工清单 {args.csv}（{n} 行）")
        return 0
```

改成：

```python
        n = write_csv(args.csv, rep)
        log(f"完成：本轮处理 {processed} 个，人工清单 {args.csv}（{n} 行）")
        try:
            from import_offer_map import refresh_table
            m = refresh_table(rep.get("items") or [])
            log(f"taobao_offer_map 已刷新（{m} 行）")
        except Exception as e:  # 刷新失败不影响匹配任务退出码，页面只是暂时用旧映射
            log(f"!! taobao_offer_map 刷新失败（不影响本轮结果）：{e}")
        return 0
```

- [ ] **Step 2: 语法 + 导入自检（不跑真实匹配）**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing && ../venv/bin/python -m py_compile isv_sku_match.py && ../venv/bin/python test_isv_sku_match.py`
Expected: 无输出（编译通过）+ `all ok`（原有测试不被破坏）。

- [ ] **Step 3: 确认改动不碰窗口防弹逻辑**

Run: `grep -n "quiet=True\|minimize" /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/isv_sku_match.py | head`
Expected: 原有 `open_page(..., quiet=True)` 调用仍在、未新增任何 new_page/minimize 变更。

---

### Task 4: 后端——VO + Mapper + Service + Controller + LowStockParamTest

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/mall/LowStockRowVo.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/mall/LowStockSpecVo.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/vo/mall/LowStockTaobaoItemVo.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/LowStockMapper.java`
- Create: `spzx-manager/src/main/resources/mapper/LowStockMapper.xml`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/LowStockService.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/LowStockController.java`
- Test: `spzx-manager/src/test/java/com/joker/spzx/manager/service/LowStockParamTest.java`

**Interfaces:**
- Consumes: Task 1 的表 `taobao_offer_map`；表 `source_sku(source_product_id, sku_key, stock, price, is_deleted)`、`source_product(source_product_name, source_product_url, is_deleted)`。
- Produces: `GET /admin/lowStock/list?threshold=&keyword=&page=&size=` → `Result<IPage<LowStockRowVo>>`。`LowStockRowVo{sourceProductId,title,sourceUrl,offerId,taobaoItems:List<Long>,minStock,lowSpecCount,lowSpecs:List<LowStockSpecVo>}`；`LowStockSpecVo{sourceProductId,skuKey,stock,price}`；`LowStockTaobaoItemVo{sourceProductId,taobaoItemId,offerId}`。Task 5 前端按此结构渲染。

- [ ] **Step 1: 写参数测试（先红）**

```java
package com.joker.spzx.manager.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/** 低库存规格页参数白名单（纯 JUnit，不拉 Spring 上下文） */
class LowStockParamTest {

    @Test
    void 阈值白名单三档原样通过() {
        assertEquals(10, LowStockService.normalizeThreshold("10"));
        assertEquals(20, LowStockService.normalizeThreshold("20"));
        assertEquals(50, LowStockService.normalizeThreshold("50"));
    }

    @Test
    void 缺省与空白用默认20() {
        assertEquals(20, LowStockService.normalizeThreshold(null));
        assertEquals(20, LowStockService.normalizeThreshold(""));
        assertEquals(20, LowStockService.normalizeThreshold("  "));
        assertEquals(20, LowStockService.normalizeThreshold(" 20 "));
    }

    @Test
    void 白名单外回null由controller转400() {
        // spec 定死三档，多传一个 15 不该静默放行去查库
        assertNull(LowStockService.normalizeThreshold("15"));
        assertNull(LowStockService.normalizeThreshold("0"));
        assertNull(LowStockService.normalizeThreshold("-10"));
        assertNull(LowStockService.normalizeThreshold("abc"));
    }

    @Test
    void 分页参数缺省与夹取() {
        assertEquals(1, LowStockService.normalizeInt(null, 1, 1, 100000));
        assertEquals(20, LowStockService.normalizeInt(null, 20, 1, 100));
        assertEquals(1, LowStockService.normalizeInt(0, 20, 1, 100));
        assertEquals(100, LowStockService.normalizeInt(500, 20, 1, 100));
        assertEquals(7, LowStockService.normalizeInt(7, 20, 1, 100));
    }
}
```

- [ ] **Step 2: 编译确认失败（红）**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"; mvn test -pl spzx-manager -am -Dtest=LowStockParamTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: COMPILATION ERROR（`LowStockService` 不存在）。

- [ ] **Step 3: 写三个 VO**

`LowStockRowVo.java`：

```java
package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 低库存规格页一行 = 一个货源商品（source_product）。只读：数据由 automation/sourcing 链路维护。
 * taobaoItems/lowSpecs 由 service 在分组页查出后回填（三段式查询，避免 GROUP_CONCAT 截断）。
 */
@Data
public class LowStockRowVo {

    private Long sourceProductId;

    /** source_product_name；采集没给标题时前端回退显示 offer_id */
    private String title;

    /** 1688 货源页 URL */
    private String sourceUrl;

    /** 1688 offerId；无映射时为 null，前端显示「未匹配」 */
    private Long offerId;

    /** 关联淘宝商品 itemId 列表（一个货源挂多件是正常态） */
    private List<Long> taobaoItems;

    /** 该货源低库存规格的最低库存 */
    private Integer minStock;

    /** 低于阈值的规格数 */
    private Integer lowSpecCount;

    /** 低库存规格明细（按 stock 升序） */
    private List<LowStockSpecVo> lowSpecs;
}
```

`LowStockSpecVo.java`：

```java
package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.math.BigDecimal;

/** 低库存规格明细一行。sourceProductId 供 service 回填装配，前端忽略。 */
@Data
public class LowStockSpecVo {

    private Long sourceProductId;

    /** 规格名（source_sku.sku_key） */
    private String skuKey;

    private Integer stock;

    private BigDecimal price;
}
```

`LowStockTaobaoItemVo.java`：

```java
package com.joker.spzx.model.vo.mall;

import lombok.Data;

/** taobao_offer_map 查询行：货源 -> 淘宝商品映射。 */
@Data
public class LowStockTaobaoItemVo {

    private Long sourceProductId;

    private Long taobaoItemId;

    private Long offerId;
}
```

- [ ] **Step 4: 写 Mapper 接口 + XML**

`LowStockMapper.java`：

```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import com.joker.spzx.model.vo.mall.LowStockSpecVo;
import com.joker.spzx.model.vo.mall.LowStockTaobaoItemVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 低库存规格页只读查询。写入方是 automation/sourcing（采集/同步/映射导入），这里只查不改。
 */
@Mapper
public interface LowStockMapper {

    /** 分组的货源页：只算 minStock/lowSpecCount，映射与明细由另两条按页内 id 补齐 */
    IPage<LowStockRowVo> selectLowStockGroups(IPage<LowStockRowVo> page,
                                              @Param("threshold") int threshold,
                                              @Param("keyword") String keyword);

    List<LowStockTaobaoItemVo> selectTaobaoItems(@Param("ids") List<Long> ids);

    List<LowStockSpecVo> selectLowSpecs(@Param("ids") List<Long> ids,
                                        @Param("threshold") int threshold);
}
```

`LowStockMapper.xml`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.joker.spzx.manager.mapper.LowStockMapper">

    <!-- 低库存规格页（只读），三段式现算：
         1. 分组的货源页（IPage 自动分页）；
         2. 该页货源的淘宝映射（taobao_offer_map，可空）；
         3. 该页货源的低规格明细。
         不 GROUP_CONCAT 聚合成一个 JSON（有截断风险），由 service 装配。
         <10 红 / 10~19 橙的红线在前端固定展示，与 threshold 档位无关。 -->
    <select id="selectLowStockGroups" resultType="com.joker.spzx.model.vo.mall.LowStockRowVo">
        SELECT sp.id                  AS sourceProductId,
               sp.source_product_name AS title,
               sp.source_product_url  AS sourceUrl,
               MIN(sku.stock)         AS minStock,
               COUNT(*)               AS lowSpecCount
        FROM source_sku sku
        JOIN source_product sp ON sp.id = sku.source_product_id AND sp.is_deleted = 0
        WHERE sku.is_deleted = 0
          AND sku.stock IS NOT NULL
          AND sku.stock &lt; #{threshold}
        <if test="keyword != null">
            AND sp.source_product_name LIKE CONCAT('%', #{keyword}, '%')
        </if>
        GROUP BY sp.id, sp.source_product_name, sp.source_product_url
        ORDER BY minStock ASC, sp.id ASC
    </select>

    <select id="selectTaobaoItems" resultType="com.joker.spzx.model.vo.mall.LowStockTaobaoItemVo">
        SELECT m.source_product_id AS sourceProductId,
               m.taobao_item_id    AS taobaoItemId,
               m.offer_id          AS offerId
        FROM taobao_offer_map m
        WHERE m.source_product_id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        ORDER BY m.taobao_item_id
    </select>

    <select id="selectLowSpecs" resultType="com.joker.spzx.model.vo.mall.LowStockSpecVo">
        SELECT sku.source_product_id AS sourceProductId,
               sku.sku_key           AS skuKey,
               sku.stock             AS stock,
               sku.price             AS price
        FROM source_sku sku
        WHERE sku.is_deleted = 0
          AND sku.stock IS NOT NULL
          AND sku.stock &lt; #{threshold}
          AND sku.source_product_id IN
        <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
        ORDER BY sku.stock ASC, sku.sku_key ASC
    </select>
</mapper>
```

- [ ] **Step 5: 写 Service**

```java
package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.mapper.LowStockMapper;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import com.joker.spzx.model.vo.mall.LowStockSpecVo;
import com.joker.spzx.model.vo.mall.LowStockTaobaoItemVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 低库存规格页（只读）：source_sku 规格级库存现算，按货源分组。
 * 1358 行量级现算毫秒级，不建物化表——物化只换来滞后（推广日报同款结论）。
 */
@Service
public class LowStockService {

    /** 阈值三档（spec 定死）；<10 红是前端固定展示，与这里的档位无关 */
    public static final Set<Integer> THRESHOLDS = Set.of(10, 20, 50);
    public static final int DEFAULT_THRESHOLD = 20;

    @Autowired
    private LowStockMapper lowStockMapper;

    /** 白名单内原样通过；空/缺省回默认 20；白名单外回 null（调用方转 400），不静默放行 */
    public static Integer normalizeThreshold(String raw) {
        if (raw == null || raw.isBlank()) {
            return DEFAULT_THRESHOLD;
        }
        try {
            int v = Integer.parseInt(raw.trim());
            return THRESHOLDS.contains(v) ? v : null;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** 缺省用 dft，越界夹取（同 ItemOpsService.normalizeInt 口径） */
    public static int normalizeInt(Integer raw, int dft, int min, int max) {
        if (raw == null) {
            return dft;
        }
        return Math.max(min, Math.min(max, raw));
    }

    public IPage<LowStockRowVo> list(String thresholdParam, String keyword, Integer page, Integer size) {
        Integer threshold = normalizeThreshold(thresholdParam);
        if (threshold == null) {
            throw new ServiceException(400, "阈值只支持 10/20/50");
        }
        long pageNum = normalizeInt(page, 1, 1, Integer.MAX_VALUE);
        long pageSize = normalizeInt(size, 20, 1, 100);
        String kw = (keyword == null || keyword.isBlank()) ? null : keyword.trim();

        IPage<LowStockRowVo> groups = lowStockMapper.selectLowStockGroups(new Page<>(pageNum, pageSize), threshold, kw);
        if (groups.getRecords().isEmpty()) {
            return groups;
        }
        Map<Long, LowStockRowVo> byId = new HashMap<>();
        List<Long> ids = new ArrayList<>();
        for (LowStockRowVo row : groups.getRecords()) {
            row.setTaobaoItems(new ArrayList<>());
            row.setLowSpecs(new ArrayList<>());
            byId.put(row.getSourceProductId(), row);
            ids.add(row.getSourceProductId());
        }
        for (LowStockTaobaoItemVo t : lowStockMapper.selectTaobaoItems(ids)) {
            LowStockRowVo row = byId.get(t.getSourceProductId());
            if (row != null) {
                row.getTaobaoItems().add(t.getTaobaoItemId());
                if (row.getOfferId() == null) {
                    row.setOfferId(t.getOfferId());
                }
            }
        }
        for (LowStockSpecVo s : lowStockMapper.selectLowSpecs(ids, threshold)) {
            LowStockRowVo row = byId.get(s.getSourceProductId());
            if (row != null) {
                row.getLowSpecs().add(s);
            }
        }
        return groups;
    }
}
```

- [ ] **Step 6: 写 Controller**

```java
package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.LowStockService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 低库存规格页：1688 货源规格级低库存（source_sku.stock < 阈值），按货源分组，纯只读。
 * 阈值白名单 10/20/50；库存数据来自 automation/sourcing 采集链路，映射表
 * taobao_offer_map 由 sku_match_report.json 导入、isv_sku_match.py 每轮刷新。
 */
@RestController
@Tag(name = "低库存规格", description = "1688 货源规格级低库存只读页")
@RequestMapping("/admin/lowStock")
public class LowStockController {

    @Autowired
    private LowStockService lowStockService;

    @Operation(summary = "低库存货源分组分页（threshold 白名单 10/20/50，非法值 400）")
    @GetMapping("/list")
    public Result<IPage<LowStockRowVo>> list(@RequestParam(required = false) String threshold,
                                             @RequestParam(required = false) String keyword,
                                             @RequestParam(required = false, defaultValue = "1") Integer page,
                                             @RequestParam(required = false, defaultValue = "20") Integer size) {
        return Result.build(lowStockService.list(threshold, keyword, page, size));
    }
}
```

- [ ] **Step 7: install model + 跑测试（绿）**

Run: `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"; mvn install -pl spzx-model -DskipTests -q && mvn test -pl spzx-manager -am -Dtest=LowStockParamTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: BUILD SUCCESS，Tests run: 4, Failures: 0。

- [ ] **Step 8: SQL 口径对数（不依赖起服务）**

Run: `/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e "SELECT COUNT(*) AS offers_20, SUM(cnt) AS specs_20 FROM (SELECT sp.id, COUNT(*) cnt FROM source_sku sku JOIN source_product sp ON sp.id=sku.source_product_id AND sp.is_deleted=0 WHERE sku.is_deleted=0 AND sku.stock IS NOT NULL AND sku.stock<20 GROUP BY sp.id) t;"`
Expected: offers_20≈186（±10 可接受，采集在持续变化）、specs_20≈1358（±50）。这个数就是接口 threshold=20 的第一页总量级，Task 6 页面核对用。

---

### Task 5: 前端——api + 路由 + lowStock.vue

**Files:**
- Create: `/Users/qyk9527/webstormProject/spzx-admin/src/api/lowStock.js`
- Modify: `/Users/qyk9527/webstormProject/spzx-admin/src/router/modules/mall.js`（import 区 + children 末尾）
- Create: `/Users/qyk9527/webstormProject/spzx-admin/src/views/mall/lowStock.vue`

**Interfaces:**
- Consumes: Task 4 的 `GET /admin/lowStock/list` 与 `LowStockRowVo` 结构（`data.records` / `data.total`，与 promoReport.vue 的 `{ data } = await ...` 解构同款）。

- [ ] **Step 1: 写 api**

```js
import request from '@/utils/request'

const api_name = '/admin/lowStock'

// threshold 白名单 10/20/50（非法值后端 400）；keyword 匹配货源标题；page/size 分页
export const GetLowStockList = query => {
  return request({
    url: `${api_name}/list`,
    method: 'get',
    params: query,
    silent: true,
  })
}
```

- [ ] **Step 2: 注册路由**

`mall.js` import 区（第 21 行 `const promoPlan = ...` 之后）加：

```js
const lowStock = () => import('@/views/mall/lowStock.vue')
```

children 数组里 `promoPlan` 那项（`/promoPlan` 块）之后加：

```js
      {
        path: '/lowStock',
        name: 'lowStock',
        component: lowStock,
        meta: {
          title: '低库存规格',
        },
        hidden: false,
      },
```

（route `name: 'lowStock'` 必须与 sys_menu 的 component 值一致，侧边栏按它匹配。）

- [ ] **Step 3: 写页面**

```vue
<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-radio-group v-model="query.threshold" size="small" @change="onSearch">
          <el-radio-button :value="10">≤10</el-radio-button>
          <el-radio-button :value="20">≤20</el-radio-button>
          <el-radio-button :value="50">≤50</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="query.keyword"
          placeholder="按货源标题搜索"
          clearable
          size="small"
          style="width: 240px"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-button type="primary" size="small" @click="onSearch">查询</el-button>
        <span class="hint">红线固定库存&lt;10 红、10~19 橙；数据截至最近一次 1688 采集/同步</span>
      </div>

      <el-table :data="rows" v-loading="loading" row-key="sourceProductId">
        <el-table-column type="expand">
          <template #default="{ row }">
            <el-table :data="row.lowSpecs" size="small" border>
              <el-table-column prop="skuKey" label="规格" min-width="160" />
              <el-table-column label="库存" width="110">
                <template #default="{ row: s }">
                  <el-tag :type="stockTagType(s.stock)" size="small">{{ s.stock }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="价格" width="100">
                <template #default="{ row: s }">{{ s.price == null ? '-' : '¥' + s.price }}</template>
              </el-table-column>
            </el-table>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="货源标题" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title || ('offer ' + (row.offerId ?? row.sourceProductId)) }}</template>
        </el-table-column>
        <el-table-column label="1688 货源" width="100">
          <template #default="{ row }">
            <a v-if="row.sourceUrl" :href="row.sourceUrl" target="_blank">打开</a>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="淘宝商品" min-width="190">
          <template #default="{ row }">
            <template v-if="row.taobaoItems && row.taobaoItems.length">
              <a
                v-for="tid in row.taobaoItems"
                :key="tid"
                :href="'https://item.taobao.com/item.htm?id=' + tid"
                target="_blank"
                class="tb-item"
              >{{ tid }}</a>
            </template>
            <span v-else class="unmatched">未匹配</span>
          </template>
        </el-table-column>
        <el-table-column label="最低库存" width="100">
          <template #default="{ row }">
            <el-tag :type="stockTagType(row.minStock)" size="small">{{ row.minStock }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lowSpecCount" label="低规格数" width="90" />
      </el-table>

      <el-pagination
        v-model:current-page="query.page"
        v-model:page-size="query.size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="load"
        @size-change="onSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { GetLowStockList } from '@/api/lowStock'

const route = useRoute()
const router = useRouter()

// 阈值/搜索写进 URL query，刷新不丢；白名单外回默认 20（后端同样校验，白名单外会 400）
const THRESHOLDS = [10, 20, 50]
const thresholdFromUrl = () => {
  const v = Number(route.query.threshold)
  return THRESHOLDS.includes(v) ? v : 20
}

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({
  threshold: thresholdFromUrl(),
  keyword: (route.query.keyword || '').toString(),
  page: 1,
  size: 20,
})

const stockTagType = stock => (stock < 10 ? 'danger' : 'warning')

const syncUrl = () => {
  router.replace({
    query: { ...route.query, threshold: query.threshold, keyword: query.keyword || undefined },
  })
}

const load = async () => {
  loading.value = true
  try {
    const { data } = await GetLowStockList({
      threshold: query.threshold,
      keyword: query.keyword || undefined,
      page: query.page,
      size: query.size,
    })
    rows.value = data?.records ?? []
    total.value = Number(data?.total ?? 0)
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  query.page = 1
  syncUrl()
  load()
}

const onSizeChange = () => {
  query.page = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.hint {
  color: #999;
  font-size: 12px;
  margin-left: 4px;
}
.tb-item {
  margin-right: 8px;
}
.unmatched {
  color: #999;
}
</style>
```

- [ ] **Step 4: 构建自检**

Run: `cd /Users/qyk9527/webstormProject/spzx-admin && npm run build 2>&1 | tail -5`
Expected: 无语法/导入报错（build 产物正常结束；本仓库无 lint 工具链，build 通过即够）。

---

### Task 6: 端到端验证 + 一致性门 + 留痕

**Files:**
- 无新文件（验证任务）

**Interfaces:**
- Consumes: Task 1-5 全部产物。

- [ ] **Step 1: 后端就绪检查**

Run: `curl -m3 -o /dev/null -w '%{http_code}' localhost:8501/`
- `000`（没起）：`bash /Users/qyk9527/ideaProject/spzx-parent/scripts/start-local.sh` 起后端（脚本会自己 `mvn package`，检测到 maven 并发会退出——先确认没有别的 mvn 在跑），等 `Started ManagerApplication`。
- 非 `000`（别人占着）：需要重启才载得进新 controller——**在它自己的启动方式里重启**（脚本管不到别的会话起的进程），或请用户重启；绝不 kill 不是本脚本起的进程。

- [ ] **Step 2: 接口冒烟（带登录态）**

管理接口在登录拦截后面。优先用 swagger 白名单通道人工走查 `/doc.html`；若要 curl，先从用户已登录的浏览器会话拿 token（或让用户在页面上点一遍代替）。核对点：
- `threshold=20` 第一页 records 非空、`total` ≈ Task 4 Step 8 的 offers_20；
- `threshold=15` 返回 `code 400`「阈值只支持 10/20/50」；
- 带 `keyword` 时 total 变小、records 标题都含关键词。

- [ ] **Step 3: 一致性门**

Run: `python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/check-consistency.py`
Expected: 不新增失败（新增 controller 端点 + 前端 api 调用点应在门 B 里对上；出现新失败先修再收工）。

- [ ] **Step 4: 页面人工走查（请用户配合）**

请用户刷新后台页面核对：运营管理下出现「低库存规格」菜单（管理员 role_id=9）；三档阈值切换、搜索、展开行红/橙、淘宝商品外跳新窗口、未匹配货源显示「未匹配」；URL 带 `?threshold=10` 刷新后档位保持。

- [ ] **Step 5: 留痕**

Run: `python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/log_work.py --module 其它 --title "低库存规格页面上线（映射表+接口+前端）" --progress "任务6步：DDL/导入/刷新/后端/前端/E2E"`
Expected: 写进当天日程（create_by=-1，不影响 23:30 自动条目）。

- [ ] **Step 6: 不 commit**

本仓库硬规则：改动留在工作区，等用户明确要求才提交。收尾时 `git status` 列出涉及文件清单汇报即可。
