# 大扫除遗留项（CORS/fastjson/@TableLogic）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口 2026-09-20 后端大扫除的三项遗留：CORS 收紧、fastjson 升级、@TableLogic 全局逻辑删除。

**Architecture:** CORS 在 `WebMvcConfiguration.addCorsMappings` 白名单化；fastjson 只动 `pom.xml` 版本号；@TableLogic 注解加在 `BaseEntity.isDeleted` 上，22 个 BaseEntity 子实体自动获得软删，手工 `setIsDeleted(1)+updateById` 全部转为 `removeById`（否则 SET 子句排除逻辑字段、静默不生效），BaseEntity 实体上的手工 `.eq(getIsDeleted,0)` 冗余过滤移除（Model 基类的保留）。

**Tech Stack:** Spring Boot 3.3.5 / MyBatis-Plus 3.5.9 / fastjson 2.0.x

## Global Constraints

- 需求源：`docs/superpowers/audits/2026-09-20-backend-cleanup-audit.md`（批4#2 + 拍板 C/D）
- 编译需先 `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`；`mvn install -pl spzx-model -DskipTests -q && mvn package -pl spzx-manager -am -DskipTests -q`
- 无测试套件，禁 `mvn test`；验证 = 编译 + 打包 + 重启 8501 冒烟
- 重启：`lsof -ti:8501 | xargs kill; sleep 1; nohup java -jar spzx-manager/target/spzx-manager.jar > /tmp/spzx-manager.log 2>&1 &`，等 `Started ManagerApplication`
- 冒烟探针（重启后必跑）：`curl -s http://127.0.0.1:8501/admin/kw/config` → `{"code":208,...}`；`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "select count(*) from kw_provider"` → 3
- kw 链路实体（KwProvider/KwTaskWord/KwTitleSuggestion）extends `Model` 非 BaseEntity → 本轮零影响、零改动
- 不 commit 无关脏文件（target/、.DS_Store、未跟踪 docs/）
- 每任务一个 commit（conventional，勿 push）

---

### Task 1: CORS 收紧为本地开发白名单

**Files:**
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/config/WebMvcConfiguration.java:28-34`

**Interfaces:** 无跨任务依赖。

- [ ] **Step 1: 修改 addCorsMappings**

```java
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowCredentials(true)
                .allowedOrigins("http://localhost:3001", "http://127.0.0.1:3001")
                .allowedMethods("*")
                .allowedHeaders("*");
    }
```

说明：前端 dev server 在 3001（`vite.config.js`），axios baseURL 绝对地址直连 8501，浏览器 origin 是 localhost:3001 或 127.0.0.1:3001。生产 nginx 同源反代不经 CORS。用 `allowedOrigins`（精确值）而非 patterns。

- [ ] **Step 2: 编译打包**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn package -pl spzx-manager -am -DskipTests -q
```

Expected: BUILD SUCCESS

- [ ] **Step 3: 重启 8501 + 冒烟**

重启（见 Global Constraints）后：

```bash
# 允许的 origin：应回 Access-Control-Allow-Origin: http://localhost:3001
curl -s -i -X OPTIONS http://127.0.0.1:8501/admin/system/index/genVarifyCode \
  -H "Origin: http://localhost:3001" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"
# 非白名单 origin：应无输出（拒绝）
curl -s -i -X OPTIONS http://127.0.0.1:8501/admin/system/index/genVarifyCode \
  -H "Origin: http://evil.example" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin"
```

Expected: 第一条有输出，第二条无输出。另跑 kw/config 208 探针。

- [ ] **Step 4: Commit**

```bash
git add spzx-manager/src/main/java/com/joker/spzx/manager/config/WebMvcConfiguration.java
git commit -m "fix(security): CORS 收紧为本地开发域名白名单"
```

---

### Task 2: fastjson 2.0.21 → 2.0.65

**Files:**
- Modify: `pom.xml:29`（`<fastjson.version>2.0.21</fastjson.version>` → `2.0.65`）

**Interfaces:** 无。fastjson 消费点（已盘点）：LoginAuthInterceptor、SysUserServiceImpl、WxLoginServiceImpl、MallRefundReportController、common-log LogUtil、common-util DefaultExcelListener。kw 链路不用 fastjson。

- [ ] **Step 1: 改版本号**

`pom.xml:29`: `<fastjson.version>2.0.21</fastjson.version>` → `<fastjson.version>2.0.65</fastjson.version>`（Maven Central 已确认存在该版本）

- [ ] **Step 2: 编译打包（触发依赖下载）**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn install -pl spzx-model -DskipTests -q && mvn package -pl spzx-manager -am -DskipTests -q
```

Expected: BUILD SUCCESS（首次会从 Central 下载 fastjson 2.0.65；若网络失败改用 `~/.m2` 已有最近的 2.0.4x 版本并记录）

- [ ] **Step 3: 重启 8501 + 冒烟**

探针（Global Constraints）+ fastjson 反序列化路径验证：

```bash
TOKEN=$(redis-cli --scan --pattern 'user:login:*' | grep -v validatecode | head -1 | sed 's/^user:login://')
curl -s http://127.0.0.1:8501/admin/system/index/getUserInfo -H "token: $TOKEN" | head -c 120
```

Expected: `{"code":200,...}`（JSON.parseObject 解析会话 JSON 正常）。写入路径（JSONObject.toJSONString 存会话、LogUtil 序列化）由 Task 3 的角色增删端到端自然覆盖。

- [ ] **Step 4: Commit**

```bash
git add pom.xml
git commit -m "chore(deps): fastjson 2.0.21 -> 2.0.65（CVE 修复）"
```

---

### Task 3: @TableLogic 全局逻辑删除

**Files:**
- Modify: `spzx-model/src/main/java/com/joker/spzx/model/entity/base/BaseEntity.java`（isDeleted 加 @TableLogic）
- Modify 6 处手工软删转 removeById（BaseEntity 实体，否则静默失效）：
  - `spzx-manager/.../service/impl/SysUserServiceImpl.java:147-153` deleteSysUser → 方法体改 `this.removeById(id);`
  - `spzx-manager/.../service/impl/SysRoleServiceImpl.java:57-63` deleteSysRole → 同上
  - `spzx-manager/.../service/impl/SysMenuServiceImpl.java:90-96` deleteData → 同上（保留 @CacheEvict）
  - `spzx-manager/.../service/impl/ProductServiceImpl.java:102-116` deleteData → `this.removeById(id);` + ProductDetails 也是 BaseEntity，`.set(getIsDeleted,1)` 改 `productDetailsMapper.delete(new LambdaQueryWrapper<ProductDetails>().eq(ProductDetails::getProductId, id));`（mapper.delete 在 @TableLogic 下= 逻辑删）
  - `spzx-manager/.../service/impl/ProductSpecServiceImpl.java`（:48 setIsDeleted(1) 处）→ `this.removeById(id);`
  - `spzx-manager/.../service/impl/OrderSourceRelationServiceImpl.java`（:80 处）→ `this.removeById(id);`
- Modify 移除冗余 `.eq(<Entity>::getIsDeleted, 0)`（仅 BaseEntity 实体，31 处）：ProductSpec×2、OrderSourceRelation×3、SysRole×2、OrderInfo×1、OrderBind×1、Category×1、NovelChapter×1、SysMenu×2、SysUser×3、ProfitAnalysisRecord×2、FeeBenchmark×2、Product×2、SkuBindRelation×3、SysWechatUser×3、Brand×2
- **保留不动**（Model 基类/自有 isDeleted，移除会导致漏过滤）：SourceFactory×2、SysRoleMenu×2（SysRoleMenuServiceImpl + SysMenuServiceImpl 各 1）、ProductBindRelation×2、ProductUnit×1；以及 UserCostServiceImpl:76、SourceFactoryServiceImpl:103 的手工 setIsDeleted(1)（Model 基类，手工软删仍有效）
- **行为变化（预期内，不改代码）**：`removeById` 类硬删转软删 —— OrderBindController:46、NovelController:122、ProfitAnalysisRecordServiceImpl:52/57/64、assignRole 的 sysUserRoleMapper.delete（sys_role_user 无唯一键，已核实无重插冲突）

**Interfaces:** 无跨任务依赖。前置 DB 校验已由计划编制完成：41 张含 is_deleted 的表 0 行 NULL/非法值；sys_role_user 无唯一索引。

- [ ] **Step 1: BaseEntity 加注解**

```java
import com.baomidou.mybatisplus.annotation.TableLogic;
...
    @Schema(description = "是否删除")
    @TableField("is_deleted")
    @TableLogic
    private Integer isDeleted;
```

- [ ] **Step 2: 6 处手工软删转 removeById（逐处 edit，方法体替换如上 Files 清单）**

每处改完立即 grep 确认：`grep -rn "setIsDeleted(1)" --include="*.java" spzx-manager/src/main` 只应剩 UserCostServiceImpl:76 与 SourceFactoryServiceImpl:103 两处。

- [ ] **Step 3: 移除 31 处 BaseEntity 冗余过滤**

逐文件删 `.eq(Xxx::getIsDeleted, 0)` 链式段（注意有的带逗号结尾、有的带分号）。完成后：

```bash
grep -rn "getIsDeleted, 0)" --include="*.java" spzx-manager/src/main | grep -v "SourceFactory\|SysRoleMenu\|ProductBindRelation\|ProductUnit" | wc -l
```

Expected: `0`

- [ ] **Step 4: 编译打包**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn install -pl spzx-model -DskipTests -q && mvn package -pl spzx-manager -am -DskipTests -q
```

Expected: BUILD SUCCESS

- [ ] **Step 5: 重启 + 冒烟（读路径）**

Global Constraints 探针 + 既有会话验证：

```bash
TOKEN=$(redis-cli --scan --pattern 'user:login:*' | grep -v validatecode | head -1 | sed 's/^user:login://')
curl -s http://127.0.0.1:8501/admin/system/index/getUserInfo -H "token: $TOKEN" | head -c 80
curl -s -X POST "http://127.0.0.1:8501/admin/system/sysUser/findByPage/1/10" -H "token: $TOKEN" -H 'Content-Type: application/json' -d '{"keyword":""}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('records:',len(d['data']['records']))"
```

Expected: getUserInfo code 200（拦截器走 BaseEntity 实体解析）；sysUser 6 条（@TableLogic 自动过滤未破坏查询）。

- [ ] **Step 6: 端到端软删验证（写路径，用一次性角色）**

```bash
TOKEN=...  # 同上
curl -s -X POST http://127.0.0.1:8501/admin/system/sysRole/saveSysRole -H "token: $TOKEN" -H 'Content-Type: application/json' -d '{"roleName":"TABLELOGIC_SMOKE_TMP","description":"temp"}'
RID=$(/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "select id from sys_role where role_name='TABLELOGIC_SMOKE_TMP'" 2>/dev/null)
# 找到 SysRoleController 的删除端点（@DeleteMapping）并调用，然后：
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e "select is_deleted from sys_role where id=$RID" 2>/dev/null
curl -s -X POST "http://127.0.0.1:8501/admin/system/sysRole/findByPage/1/50" -H "token: $TOKEN" -H 'Content-Type: application/json' -d '{}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('leak:',any(r['roleName']=='TABLELOGIC_SMOKE_TMP' for r in d['data']['records']))"
```

Expected: DB `is_deleted=1`（软删生效，非物理消失）；列表 `leak: False`（自动过滤生效）。此流程同时覆盖 LogUtil+fastjson 2.0.65 写路径（saveSysRole 带 @Log）。

- [ ] **Step 7: Commit**

```bash
git add spzx-model/src/main/java/com/joker/spzx/model/entity/base/BaseEntity.java \
  spzx-manager/src/main/java/com/joker/spzx/manager/service/impl/
git commit -m "refactor(cleanup): BaseEntity @TableLogic 全局逻辑删除，手工软删转 removeById"
```

---

## Self-Review

- 覆盖：拍板 C（Task 1）、拍板 D（Task 2）、批4#2（Task 3）✓
- 类型/行为一致性：6 转换点 + 31 过滤移除点均有精确 file:line 与替换体；Model 基类保留清单明确 ✓
- 无占位符；每个 task 自带编译+冒烟+commit 闭环 ✓
