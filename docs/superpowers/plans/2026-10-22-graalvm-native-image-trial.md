# GraalVM Native Image 试验（spzx-manager）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 GraalVM Native Image 把 spzx-manager 编译成原生二进制，做到完整启动 + 核心只读接口可用，并产出与 `java -jar` 的启动/内存对比数据。

**Architecture:** Spring Boot 官方 AOT 路线：spzx-manager 加默认不激活的 `native` profile（native-maven-plugin + process-aot），反射配置由 tracing agent 对现成 jar 跑一轮采集自动生成，配置 JSON 按 META-INF 约定落进 resources。spec 见 `docs/superpowers/specs/2026-10-22-graalvm-native-image-trial-design.md`。

**Tech Stack:** GraalVM 21.0.7 (Oracle) / Spring Boot 3.3.5 / Java 21 / MyBatis-Plus 3.5.9 / Maven (IDEA 内置)

## Global Constraints

- Maven 用 IDEA 内置：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`
- GraalVM 路径（已装）：`GRAALVM=/Users/qyk9527/Library/Java/JavaVirtualMachines/graalvm-jdk-21.0.7/Contents/Home`
- **试验进程一律用 8511 端口**（`--server.port=8511`）；8501 上可能有桌面开关起的 `java -jar` 后端，**绝不 kill 不是本计划启动的进程**
- **绝不与其它 maven 并发**（16G 内存超售，仓库既有规则）；动手前 `pgrep -fl maven` 确认
- 只 commit、不 push；**不 `git add -A`**，逐文件 add
- MySQL/Redis 开机自启假定在线；不在则：Redis `scripts/start-redis.sh`，MySQL `osascript -e 'do shell script "launchctl load -w /Library/LaunchDaemons/com.oracle.oss.mysql.mysqld.plist" with administrator privileges'`
- 登录走 wx mock 流程（无需验证码）；如果 mock 链路失败，后备 = 账号密码 + 从 Redis 读验证码（见 Task 4 后备步骤）
- 主类 `com.joker.spzx.manager.ManagerApplication`

---

### Task 1: spzx-manager 加 native profile

**Files:**
- Modify: `spzx-manager/pom.xml`（`<build>` 前加 `<profiles>` 节）

**Interfaces:**
- Produces: profile id `native`；Task 3 用 `mvn -Pnative` 触发；配置 JSON 目录 `spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/`（Task 2 产出）

- [ ] **Step 1: 确认无并发 maven 后，在 pom.xml 的 `</build>` 之后、`</project>` 之前插入 profiles 节**

```xml
    <profiles>
        <profile>
            <id>native</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.graalvm.buildtools</groupId>
                        <artifactId>native-maven-plugin</artifactId>
                        <configuration>
                            <mainClass>com.joker.spzx.manager.ManagerApplication</mainClass>
                            <metadataRepository>
                                <enabled>true</enabled>
                            </metadataRepository>
                        </configuration>
                        <executions>
                            <execution>
                                <id>add-reachability-metadata</id>
                                <goals>
                                    <goal>add-reachability-metadata</goal>
                                </goals>
                            </execution>
                            <execution>
                                <id>compile-native</id>
                                <goals>
                                    <goal>compile-no-fork</goal>
                                </goals>
                                <phase>package</phase>
                            </execution>
                        </executions>
                    </plugin>
                    <plugin>
                        <groupId>org.springframework.boot</groupId>
                        <artifactId>spring-boot-maven-plugin</artifactId>
                        <executions>
                            <execution>
                                <id>process-aot</id>
                                <goals>
                                    <goal>process-aot</goal>
                                </goals>
                            </execution>
                        </executions>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
```

（版本不用写：spring-boot-starter-parent 3.3.5 的 pluginManagement 已管理 native-maven-plugin；profile 内的 spring-boot 插件执行会与主 `<build>` 里的同名插件合并。）

- [ ] **Step 2: 验证 profile 可激活且构建仍通过**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn help:active-profiles -pl spzx-manager -Pnative 2>&1 | grep -A 3 'Active Profiles'
mvn compile -pl spzx-manager -am -q
```

Expected: Active Profiles 列出 `native`；compile 静默通过（不带 `-Pnative` 时 profile 不激活，JVM 构建零影响）。

- [ ] **Step 3: Commit**

```bash
git add spzx-manager/pom.xml
git commit -m "build: spzx-manager 增加 native profile（GraalVM 试验，默认不激活）"
```

---

### Task 2: 构建 JVM jar + tracing agent 采集反射配置

**Files:**
- Create: `spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/`（agent 生成 4 类 JSON）
- Modify: 无手改文件

**Interfaces:**
- Consumes: Task 1 的 profile id（本任务不用 native profile，只产 jar）
- Produces: `spzx-manager/target/spzx-manager.jar`；JSON 配置目录（Task 3 编译时被 native-image 自动拾取）

- [ ] **Step 1: 构建 JVM jar（仓库既有打包命令）**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn package -pl spzx-manager -am -DskipTests -q
ls -lh spzx-manager/target/spzx-manager.jar
```

Expected: jar 存在且比 src/main 新。

- [ ] **Step 2: 前置检查（端口 + Redis + 无并发 maven）**

```bash
lsof -ti:8511 && echo "8511 被占，先处理" || echo "8511 空闲"
redis-cli ping
pgrep -fl maven || echo "无并发 maven"
```

Expected: 8511 空闲、PONG、无并发。

- [ ] **Step 3: 用 GraalVM 的 java 带 agent 起服务（后台，日志落 /tmp）**

```bash
GRAALVM=/Users/qyk9527/Library/Java/JavaVirtualMachines/graalvm-jdk-21.0.7/Contents/Home
mkdir -p spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager
"$GRAALVM/bin/java" \
  -agentlib:native-image-agent=config-output-dir=spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager \
  -jar spzx-manager/target/spzx-manager.jar \
  --spring.profiles.active=dev --server.port=8511 > /tmp/spzx_agent_run.log 2>&1 &
echo $! > /tmp/spzx_agent_run.pid
```

- [ ] **Step 4: 等 20 秒，确认启动成功**

```bash
sleep 20
grep -c 'Started ManagerApplication' /tmp/spzx_agent_run.log
```

Expected: 输出 1。若 0：`tail -50 /tmp/spzx_agent_run.log` 看异常再处理。

- [ ] **Step 5: 走 wx mock 登录拿 token，再踩 4 个只读 GET**

```bash
TICKET=$(curl -s -X POST http://localhost:8511/admin/system/index/wxLogin/create \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['ticket'])")
curl -s "http://localhost:8511/admin/system/index/wxLogin/mockScan?ticket=$TICKET" > /dev/null
curl -s "http://localhost:8511/admin/system/index/wxLogin/mockConfirm?ticket=$TICKET" > /dev/null
TOKEN=$(curl -s "http://localhost:8511/admin/system/index/wxLogin/status?ticket=$TICKET" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
echo "token=$TOKEN"
for EP in kpi effectTrend taskAnomalies recentLogs; do
  echo "== /admin/dashboard/$EP"
  curl -s -H "token: $TOKEN" "http://localhost:8511/admin/dashboard/$EP" | head -c 200; echo
done
```

Expected: token 非空（JSON 解析失败 → 走 Task 4 的后备登录）；4 个接口返回 `{"code":200,...}` 或等价成功 JSON。这一步会把 MP lambda wrapper、fastjson2、Redis、mapper XML 全踩到，agent 全程记录。

- [ ] **Step 6: 优雅停机（agent 在 JVM 退出时才写盘）**

```bash
kill $(cat /tmp/spzx_agent_run.pid)
sleep 5
ls spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/
```

Expected: 出现 `reflect-config.json`、`resource-config.json`、`proxy-config.json`、`jni-config.json` 等文件。

- [ ] **Step 7: 验配置抓到了关键类 + 防 filtering 破坏**

```bash
grep -l 'SysUser' spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/reflect-config.json
grep -c 'mapper' spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/resource-config.json
grep -rn '\${' spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/*.json | head -3
```

Expected: 前两条有命中；第三条**无输出**。若出现 `${`：resources filtering 会破坏这些 JSON，需在 pom `<resources>` 里给 `META-INF/native-image/**` 加一条 filtering=false 的前置 resource 规则，重跑 Task 2。

- [ ] **Step 8: Commit**

```bash
git add spzx-manager/src/main/resources/META-INF/native-image/
git commit -m "build: tracing agent 采集 native 反射/资源/代理配置"
```

---

### Task 3: Native 编译

**Files:**
- Modify（仅当触发后备）: `spzx-manager/pom.xml`
- Create: `spzx-manager/target/spzx-manager`（原生二进制，gitignore 的 target，不入库）

**Interfaces:**
- Consumes: Task 1 的 profile、Task 2 的配置 JSON
- Produces: `spzx-manager/target/spzx-manager` 可执行文件（Task 4/5 使用）

- [ ] **Step 1: 前置检查（无并发 maven；机器空闲内存 ≥8G）**

```bash
pgrep -fl maven || echo "无并发 maven"
memory_pressure | head -2
```

- [ ] **Step 2: GraalVM 作 JAVA_HOME 编译（预计 5-15 分钟，峰值 6-8G 内存）**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
export JAVA_HOME=/Users/qyk9527/Library/Java/JavaVirtualMachines/graalvm-jdk-21.0.7/Contents/Home
mvn -Pnative -pl spzx-manager -am package -DskipTests
ls -lh spzx-manager/target/spzx-manager
```

Expected: `BUILD SUCCESS`，`spzx-manager` 二进制存在（几十 MB）。构建日志会先跑 `process-aot` 再 `native-image`。
**注意**：`-pl spzx-manager -am` 下上游模块（spzx-model/common-*）不受 `-Pnative` 影响——本仓的 native profile 只定义在 spzx-manager 自己的 pom 里，上游模块即使继承了 Boot parent 的同名 profile 也只是 pluginManagement、无执行。
**其它构建期错误**（如某库静态初始化/反射缺配置）：按报错类名在 Task 2 的配置 JSON 里手补条目后重编；补的条目随该文件一起 commit。

- [ ] **Step 3（后备，仅 Step 2 报 RestartClassLoader/devtools 相关错时）: 临时注释 devtools 重编**

在 `spzx-manager/pom.xml` 注释掉：

```xml
        <!-- GraalVM 试验期间临时注释，Task 5 收尾恢复
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-devtools</artifactId>
            <optional>true</optional>
        </dependency>
        -->
```

然后重跑 Step 2。**Task 5 收尾时必须恢复此依赖**并在恢复后跑一次 `mvn compile -pl spzx-manager -am -q` 验证。

- [ ] **Step 4（后备，仅构建期报 ClickHouse/ES 静态初始化错时）: 依赖挪进 infra profile**

把 ES、ClickHouse 两个 `<dependency>` 从主 `<dependencies>` 挪进新 profile：

```xml
    <profiles>
        <profile>
            <id>infra</id>
            <activation>
                <activeByDefault>true</activeByDefault>
            </activation>
            <dependencies>
                <dependency>
                    <groupId>com.clickhouse</groupId>
                    <artifactId>clickhouse-jdbc</artifactId>
                    <version>0.6.5</version>
                </dependency>
                <dependency>
                    <groupId>org.elasticsearch.client</groupId>
                    <artifactId>elasticsearch-rest-high-level-client</artifactId>
                    <version>7.17.9</version>
                </dependency>
            </dependencies>
        </profile>
    </profiles>
```

native 编译命令改为 `mvn -Pnative,!infra -pl spzx-manager -am package -DskipTests`。**此改动是永久性的**（main pom 里依赖变 profile），commit 时说明原因；JVM 构建默认仍带这两个依赖（activeByDefault），行为不变。

- [ ] **Step 5: Commit（若 Step 3/4 动了 pom；无改动则跳过）**

```bash
git add spzx-manager/pom.xml
git commit -m "build: native 构建适配（按实际构建错误调整）"
```

---

### Task 4: L1+L2 验证（完整启动 + 核心接口）

**Files:**
- 无文件改动；只运行与记录

**Interfaces:**
- Consumes: Task 3 的 `spzx-manager/target/spzx-manager` 二进制
- Produces: 验证记录（写进 Task 5 回填 spec 的素材）

- [ ] **Step 1: 起 native 二进制（8511，后台，日志落 /tmp）**

```bash
lsof -ti:8511 && echo "8511 被占" || true
./spzx-manager/target/spzx-manager \
  --spring.profiles.active=dev --server.port=8511 > /tmp/spzx_native_run.log 2>&1 &
echo $! > /tmp/spzx_native_run.pid
sleep 10
grep -E 'Started ManagerApplication' /tmp/spzx_native_run.log
ps -o rss= -p $(cat /tmp/spzx_native_run.pid)
```

Expected: 有 Started 行；RSS 数值记录下来（单位 KB）。**L1 通过** = 进程稳定 60 秒不退出：

```bash
sleep 50 && kill -0 $(cat /tmp/spzx_native_run.pid) && echo "L1 通过：进程存活"
```

注：口令不需要环境变量——`application-local.yml`（gitignore，classpath 内）经 `spring.config.import` 自动生效，与 java -jar 同机制。MinIO 未启动 → 启动日志可能有上传相关 WARN，属预期，不算失败。

- [ ] **Step 2: 验证码登录（Task 2 实测走通的主路）+ 4 个只读 GET**

wx mock 链路已证实走不通（mockConfirm 每票随机 openid → status 必落 5 请绑定），**不再使用**。主路 = genVarifyCode + Redis 取验证码 + 账号密码登录（admin 口令 md5=123456，本机 dev 库 sys_user 实测）：

```bash
CODEKEY=$(curl -s http://localhost:8511/admin/system/index/genVarifyCode \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['codeKey'])")
CODEVAL=$(redis-cli GET "user:login:validatecode:$CODEKEY")
TOKEN=$(curl -s -X POST http://localhost:8511/admin/system/index/login \
  -H 'Content-Type: application/json' \
  -d "{\"userName\":\"admin\",\"password\":\"123456\",\"captcha\":\"$CODEVAL\",\"codeKey\":\"$CODEKEY\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
echo "token=$TOKEN"
for EP in kpi effectTrend taskAnomalies recentLogs; do
  echo "== $EP"; curl -s -o /dev/null -w '%{http_code}\n' -H "token: $TOKEN" "http://localhost:8511/admin/dashboard/$EP"
done
```

注：`user:login:` 前缀来自 `Constant.USER_LOGIN_REDIS_PREFIX`；取不到验证码值就 `redis-cli --scan --pattern '*validatecode*'` 核对真实键。

Expected: token 非空；4 个接口全部 200，且返回体 code=200（抽查 `curl -s ... | head -c 200` 与 JVM 版输出结构一致）。**L2 通过** = 登录 + 4 接口全通。

- [ ] **Step 3b（仅启动期 springdoc/knife4j bean 报错时）: 禁用 API 文档重启**

```bash
kill $(cat /tmp/spzx_native_run.pid)
./spzx-manager/target/spzx-manager \
  --spring.profiles.active=dev --server.port=8511 \
  --springdoc.api-docs.enabled=false > /tmp/spzx_native_run.log 2>&1 &
echo $! > /tmp/spzx_native_run.pid
```

不影响 L1/L2 判定（doc.html 不在验收范围）。

- [ ] **Step 4: 停掉二进制，记录素材**

```bash
kill $(cat /tmp/spzx_native_run.pid)
grep -E 'Started ManagerApplication' /tmp/spzx_native_run.log | tail -1
```

把 Started 行的秒数、Step 1 的 RSS、L1/L2 结果记进 /tmp/spzx_native_result.txt（Task 5 回填用）。

（若走了 Step 3b，kill 前先记录带 --springdoc 禁用旗标这一事实，写进 Task 5 的坑位记录。）

---

### Task 5: L3 对比 + spec 回填 + 留痕收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-10-22-graalvm-native-image-trial-design.md`（§8 实测结果）
- Modify（若 Task 3 注释了 devtools）: `spzx-manager/pom.xml`（恢复）

**Interfaces:**
- Consumes: Task 2 的 jar、Task 3 的二进制、Task 4 的记录
- Produces: spec §8 对比表；台账一行

- [ ] **Step 1: java -jar 基线重测（同口径 8511）**

```bash
lsof -ti:8511 && echo "8511 被占" || true
java -jar spzx-manager/target/spzx-manager.jar \
  --spring.profiles.active=dev --server.port=8511 > /tmp/spzx_jvm_baseline.log 2>&1 &
echo $! > /tmp/spzx_jvm_baseline.pid
sleep 12
grep -E 'Started ManagerApplication' /tmp/spzx_jvm_baseline.log | tail -1
ps -o rss= -p $(cat /tmp/spzx_jvm_baseline.pid)
kill $(cat /tmp/spzx_jvm_baseline.pid)
```

Expected: 记下秒数与 RSS（与 Task 4 的 native 数据同口径对比）。

- [ ] **Step 2: 恢复 devtools（若 Task 3 注释过）+ 编译验证**

恢复 pom 里被注释的 devtools 依赖（去掉注释标记），跑：

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mvn compile -pl spzx-manager -am -q
```

Expected: 静默通过。

- [ ] **Step 3: spec §8 回填对比表**

按实测写 `docs/superpowers/specs/2026-10-22-graalvm-native-image-trial-design.md` 第 8 节，格式：

```markdown
## 8. 实测结果

日期：2026-10-22

| 指标 | java -jar（基线，当日重测） | native 二进制 | 差值 |
|---|---|---|---|
| 启动耗时（Started 行） | X s | Y s | -Z% |
| RSS 常驻内存 | X MB | Y MB | -Z% |
| 二进制/产物体积 | jar X MB | 二进制 Y MB | — |

- L1 完整启动：通过/失败（一句现象）
- L2 核心接口：mock 登录 + kpi/effectTrend/taskAnomalies/recentLogs 全 200 / 失败详情
- 构建耗时：X 分钟（native package）；构建期改动记录（devtools/infra 后备是否触发）
- 踩坑记录：…
```

- [ ] **Step 4: 台账留痕 + Commit**

```bash
python3 scripts/log_work.py --module "系统" --title "GraalVM Native Image 试验（spzx-manager）" \
  --progress "native 构建通过; L1启动通过; L2接口4/4; 启动 Xs vs Ys; 内存 XMB vs YMB" \
  --remark "spec: docs/superpowers/specs/2026-10-22-graalvm-native-image-trial-design.md §8"
git add docs/superpowers/specs/2026-10-22-graalvm-native-image-trial-design.md \
  $(git diff --name-only | grep -E 'spzx-manager/pom.xml' || true)
git commit -m "docs: GraalVM 试验实测结果回填（启动/内存对比 + 坑位）"
```

（progress 里的 X/Y 按实测替换；pom 若有改动一并提交，没有就不带。）
