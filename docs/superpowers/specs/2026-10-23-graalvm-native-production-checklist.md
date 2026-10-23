# GraalVM Native 上生产 Checklist（spzx-manager）· 收口台账

日期：2026-10-23
前置：`2026-10-22-graalvm-native-image-trial-design.md`（试验设计）+ `plans/2026-10-22-graalvm-native-image-trial.md`（执行计划）
目标形态：**本地 IDEA 用 JVM 开发，容器里用 GraalVM native 运行**。本文档是「native 上生产」的逐条收口清单，状态随验证更新。

状态图例：✅ 已通过 · ⚠️ 部分验证 · ⏳ 待验证 · ❌ 有缺口/需决策

---

## 0. 结论摘要

- ✅ native 可稳定编译（`mvn -Pnative`），启动 0.34s（含 `IdentifierGenerator` bean 修复后），`-Xmx128m` 下空闲 62MB / 暖机+写+连接池 70MB。
- ✅ 登录 + 4 个只读接口全 200；基础写（dict insert/update）返回 200。
- ⏳ 未收口：验证码、doc.html、MinIO/文件上传、全量写路径、@Scheduled 准点触发、env 驱动配置、容器化、CI 冒烟、可观测性。

---

## 1. 构建 / 打包

| 项 | 状态 | 说明 / 证据 |
|---|---|---|
| native 编译 `mvn -Pnative -pl spzx-manager -am clean package -DskipTests` | ✅ | 2026-10-23 重建成功，产物 `spzx-manager/target/spzx-manager` 256MB |
| 反射元数据（agent 配置迁至 `-agent` 目录 + 手写 `-extra`） | ✅ | 注册 13,759 types / 9,865 fields / 37,018 methods |
| buildArgs（`--initialize-at-build-time` / `--initialize-at-run-time`） | ✅ | 已固化在 `spzx-manager/pom.xml` 的 `native` profile |
| 构建必须 `clean`（增量不可靠 / 删源文件残留） | ✅ | 已固化为习惯，命令固定带 `clean` |
| 多阶段 Dockerfile（build 阶段 GraalVM，运行阶段无 JDK 极简镜像） | ⏳ | 未写；目标运行镜像 <100MB |
| CI native 冒烟（每次构建后起容器跑 启动+登录+核心接口） | ⏳ | 未做；缺它 native 会 silent break |

## 2. 配置（env 驱动 / profile 分离）

| 项 | 状态 | 说明 |
|---|---|---|
| `SPRING_DATASOURCE_PASSWORD` 等 env 占位符 | ⚠️ | dev.yml 里密码占位符 `${SPRING_DATASOURCE_PASSWORD:}` 已存在；URL/Redis host 仍硬编码 localhost |
| `application-prod.yml`（非密配置 + env 占位符，宿主名指向容器服务名） | ⏳ | 未写 |
| 运行时 `SPRING_PROFILES_ACTIVE=prod` 切 profile | ⏳ | 未验证 native 下运行时切 profile 的行为 |
| **不把 `application-local.yml`（含真实口令）烤进生产二进制** | ❌ | 当前 dev 构建会把它烤进 image；容器版必须拆走，口令只走 env/secret |
| 时区 / `file.encoding` 等 runtime 参数容器化 | ⏳ | 未约定 |

## 3. 启动命令（native 专属）

| 项 | 状态 | 说明 |
|---|---|---|
| `-Xmx128m`（封堆） | ✅ | 缺省堆上限 ≈ 物理内存 80%，不封多占 ~50MB；128m 下 62/70MB |
| `-Dslf4j.provider=ch.qos.logback.classic.spi.LogbackServiceProvider` | ✅ | 必需，否则日志静默 |
| `--spring.web.resources.add-mappings=false` | ✅ | 必需，否则 webjars ClassGraph 扫描炸 |
| 端口 / 日志重定向 / 优雅停止约定 | ⏳ | 容器侧需定（默认 8501，日志走 stdout 交容器收集） |

## 4. 功能差异（dev=JVM / prod=native 行为差）

| 项 | 状态 | 说明 |
|---|---|---|
| 登录 + kpi/effectTrend/recentLogs/taskAnomalies 4 读接口 | ✅ | 全 200，真实查库 + fastjson2 序列化 |
| 基础写（dict insert/update） | ⚠️ | 返回 200；**未验落库持久化正确性** |
| 验证码（hutool AWT） | ❌ | native 无 AWT，当前降级为随机码 + 1x1 占位图；需决策：生产关验证码 / 换非 AWT 方案 |
| doc.html / Swagger UI | ❌ | native 下被移除（`NativeCompatConfig`），404；生产可接受但需确认 |
| MinIO / 文件上传 | ⏳ | 未验证（本机 MinIO 也未起）；需补反射元数据 + 真环境回归 |
| 全量写路径（对账导入 / easyexcel 导出 / 视频生成 / 批处理） | ⏳ | 未验证；easyexcel 是重反射路径，风险高 |
| @Scheduled 准点触发 | ⚠️ | 定时任务 bean 初始化正常（启动日志见 `SyncAlertNotifyTask`）；未验证一个完整周期准点触发 |
| 微信 mock / 真实微信回调登录 | ⚠️ | mock 路径随 L2 验证过；真实回调未验 |

## 5. 长期维护纪律 / 可观测性

| 项 | 状态 | 说明 |
|---|---|---|
| 新增/升级依赖 → 重跑 tracing agent + 更新 `META-INF/native-image/**` + native 冒烟 | ⏳ | 制度化到 CI/文档；漏了是运行期 `NoClassDefFoundError` |
| 可观测性（无 jstack/jmap/attach agent，JFR 受限，无 devtools 热重载） | ⏳ | 需铺日志 + 外部指标（Prometheus 等） |
| native 二进制不外发（内烤口令） | ❌ | 与 §2 第三条同源；二进制含 dev 配置与口令，只在可信环境 |
| 内存封堆纪律（`-Xmx128m`）固化进启动脚本 | ⏳ | 待写 `start-native.sh` / 容器 entrypoint |

---

## 下一步建议（优先级）

1. **配置拆解**：写 `application-prod.yml` + 把口令/宿主从构建期拆到 env（§2）。
2. **功能收口**：验证码、MinIO、全量写路径、@Scheduled 准点（§4）。
3. **容器化**：多阶段 Dockerfile + entrypoint + CI native 冒烟（§1、§3）。
4. **可观测性**：日志/指标铺好再上（§5）。

状态与实测数据随验证更新；改完记得同步 `docs/superpowers/` 台账并跑 `python3 scripts/check-consistency.py`（如动到 controller/调度/配置）。
