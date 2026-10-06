# AGENTS.md — spzx-parent

多平台电商运营后台（Spring Boot 3.3.5 + Java 21 + MyBatis-Plus 3.5.9 单体）。「聚合支付中台」**只有设计稿、未落地**：`docs/PAYMENT_PLATFORM_ARCHITECTURE.md` 里的 PaymentFacade / PayV2Controller / PayStrategy / 状态机 / RocketMQ 事件等类**在代码中均不存在**，勿按文档找代码。

## 构建命令

```bash
# 本机未安装 mvn，用 IDEA 内置 Maven
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"

# 编译（spzx-manager 依赖 spzx-model jar，必须先 install）
mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am

# 打包 / 运行（主类 com.joker.spzx.manager.ManagerApplication，端口 8501，profile dev）
mvn package -pl spzx-manager -am -DskipTests
mvn spring-boot:run -pl spzx-manager
```

**本机一键起前后端：双击 `~/Desktop/运营后台开关.command`**（薄壳，真逻辑在 `scripts/start-local.sh|stop-local.sh`，再双击一次即停）。
- 端口有人听就复用，**从不 kill 不是它起的进程**；判据是 `~/Library/Application Support/spzx-local/pids` + 命令行二次核对（防 pid 复用误杀）
- JVM 参数（每个数字都有实测出处，见 `scripts/start-local.sh` 注释）：`-Xms48m -Xmx320m -Xss512k -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -XX:CICompilerCount=1 -XX:MinHeapFreeRatio=20 -XX:MaxHeapFreeRatio=40 -XX:MaxDirectMemorySize=64m -Dserver.tomcat.threads.max=16 -Djava.util.concurrent.ForkJoinPool.common.parallelism=1`。对照：不封顶时默认堆上限取物理内存 1/4（这台 16G = 4G），线程栈默认 2048KB，JIT 编译线程默认 4 个；实测那份 `spring-boot:run` 的后端 footprint 579MB、56 线程、空闲 CPU 4.4% 单核。**`java -jar` 里没有 DevTools**（spring-boot-maven-plugin 默认剔除，unzip 复核为 0）→ 没有每秒轮询 classpath 的重启器，而它正是 `spring-boot:run` 那份空闲 CPU 的主要来源
- **不启动 Docker Desktop**（省约 1GB）→ MinIO 9000 空着，文件上传/图片类功能会报错，其余不受影响
- jar 比 `src/main` 下任何源码新就直接用，落后了才 `mvn package`（1~2 分钟）；检测到已有 maven 在跑会报错退出，绝不并发两个（16G 超售）
- 现在 8501 这份**就是脚本自己起的**（2026-10-06 从别的会话的 `mvn spring-boot:run` 换过来，pid 记在 `~/Library/Application Support/spzx-local/pids`，再双击桌面开关即停）。实测对照：老那份 footprint 579MB / 56 线程 / 空闲 4.4%，还额外挂着一个 765MB 的 maven 父进程；新这份 282–310MB / 34 线程 / 空闲 0.2%，`Started ManagerApplication in 4.4s`。改完 Java 代码：端口空着脚本自己重新打包再起；要是端口又被别的会话用 `target/classes` 占了，那份得在它自己的启动方式里重启，脚本管不到。

**无 CI、无 mvnw、无 lint/format 工具链**——验证只能本地跑：`mvn compile` + `mvn test -Dtest=…` + **`python3 scripts/check-consistency.py`**（一致性门：调度四份副本 / 前端 217 个调用点 vs 后端 282 条路由 / 判据副本，退出码非 0 就是漂移；先 `--selftest` 证明它报得出红，再信它的绿。改 cron/LaunchAgent/注册表/卡片配置、加或删 controller 端点、动异常流量判据，都要跑它）。

## 测试

- `spzx-manager` 下 20 个测试类，**除 `EmailTest` 外全是纯 JUnit 单测**（不联网、不拉 Spring 上下文，覆盖 expense/kw/videogen/ingest/platform/promo/dashboard/itemops 等）。单跑：
  `mvn test -pl spzx-manager -Dtest=AlipayBillCsvParserTest`
- `EmailTest` 是 `@SpringBootTest`，需 MySQL/Redis 在线；**裸 `mvn test` 会带上它**——环境不全必挂，单测一律用 `-Dtest=` 指定。
- `spzx-model/src/test/java/com/joker/GeneratorCode.java` 是 MyBatis-Plus 代码生成器（非测试），outPath/tables 硬编码旧机器，勿直接跑。
- **改 `spzx-model`（实体/VO）后必须完整重启后端**：devtools 热重启只重载 `target/classes`，`spzx-model` 以 jar 进 classpath，加字段会当场 `NoSuchMethodError`（先 `mvn install -pl spzx-model` 再重启）。
- 断言与实测矛盾时先 `hexdump` 字面量：`2026-09-01` 与 `2026/09/01` 在终端里看着一模一样，但 `LocalDate.parse` 只认后者——「测试不合逻辑地通过」九成是渲染骗眼，不是构建骗人。

## 模块边界

| 模块 | 内容 |
|------|------|
| `spzx-model` | 实体/VO/DTO/枚举（无内部依赖，勿引 spzx-common） |
| `spzx-common/common-util` | 工具类、`Constant`（登录白名单） |
| `spzx-common/common-service` | Knife4j 配置、全局异常 |
| `spzx-common/common-log` | `@Log` 注解 + AOP 切面（Log4j2 starter 也在此） |
| `spzx-manager` | controller/service/mapper，唯一 Spring Boot 入口 |

## 配置要点（`application-dev.yml`）

- MySQL `localhost:3306/db_spzx`（root/root123456）、Redis `localhost:6379`（无密码）——宿主机直装，**机器重启后不自启**。
  命令行连库一律 `mysql --defaults-extra-file=/tmp/spzx_my.cnf`，**别把口令写进命令行**；这个文件会被 macOS 清 /tmp 清掉，重建：`python3 scripts/mysql-cnf.py`（从 application-dev.yml 读，写 600，`--test` 顺手连一次）。带中文的 SQL 靠它里面的 `default-character-set=utf8mb4` 才不会双重编码。
- `spring.config.import: optional:classpath:application-local.yml` — 本地覆盖文件已 gitignore，**密钥/凭据放这里，勿提交**。
- 微信扫码登录 `wx.login.mock-mode: true`：dev 登录走 mock（白名单含 mockScan/mockConfirm），无需真实微信回调。
- MinIO `127.0.0.1:9000`（minioadmin/minioadmin），bucket `spzx-manager`。
- `spzx-manager` 资源 `filtering=true`：resources 里的 `${...}` 会被 Maven 构建期替换，勿把运行期占位符写进 yml。
- ES / ClickHouse：仅 pom 引入依赖，**无任何配置与代码引用，未启用**（yml 的 `app.enable-infra` 开关也无代码绑定）；**没有 RocketMQ**（依赖都没有）。
- dev 开了 `spring.main.lazy-initialization: true`：缺 bean / 配置错误会延迟到首次调用才爆，别只看启动日志判断健康。**但 `@Scheduled` 不需要 `@Lazy(false)` 也会被调度**——本文档此前写的"不加就永不调度"已于 2026-10-03 被日志推翻：`QrLoginTicketCleanTask` 没有该注解，进程 22:00:02 启动、期间零 HTTP 请求，仍从 22:05 起每 5 分钟准点触发（共 59 次）。Boot 3.3.5 会把带 `@Scheduled` 的 bean 排除在懒初始化之外；`IngestFreshnessTask` 等三处现存的 `@Lazy(false)` 是显式保险，不是必要条件。另：devtools 热重启有时会撞上 maven 正在写 `target/classes`，日志里留下一条 `ERROR SpringApplication : Application run failed`（bean 创建失败），几秒后自动重试就 `Started ManagerApplication` 成功——**数 ERROR 做健康判据时要先看这条是不是已自愈**（2026-10-05 01:53 实测：19 秒失败、25 秒成功、端口 8501 一直在听）。
- `task-progress.config-path`、`visual.python-bin/script-dir` 硬编码本机绝对路径指向 `automation/`，仓库搬家即失效。**2026-10-07 主图质量分链路已修通**：`assess_visual.py` / `assess_main_img.py` / `generate_main_img_variants.py` 从 `_archive_20260906/` 移回 `automation/sourcing/`（后端按 `visual.script-dir` 找它们）；真正的断点不是路径而是 **venv 架构**——`automation/venv` 整批 C 扩展是 x86_64（Rosetta 时代建的），而 cron/后端按 arm64 调它，纯 Python 脚本照常跑、`import numpy/PIL.Image` 一律炸（numpy 降到 1.26.4、Pillow 重装成 arm64 才通；`av`/`tokenizers`/`hf_xet` 仍是 x86_64 但没有任何现役脚本用）。**`product_media.update_time` 是普通 datetime 没有 `ON UPDATE CURRENT_TIMESTAMP`**（`source_product.update_time` 有），所以脚本 UPDATE 必须显式 `update_time=NOW()`，否则质量分页的「分数截至」（读 `max(product_media.update_time)`）永远停在旧批次不前进。全量重跑没做：`assess_main_img.py` 不带参数是 18796 行、逐行下载 alicdn 图，属大批量外网访问，要跑先限量分轮。变体图库里存的是本机绝对路径（生成脚本没传 MinIO），浏览器加载不了，页面只显示文件名。见 spec §31
- **"这个作业几点跑"一共有三份副本**：机器上的 `crontab -l` / `~/Library/LaunchAgents/*.plist`（推广采集是 launchd 的 `com.spzx.alimama-promo`，每日 22:00，**不在 crontab 里**）、注册表 `ingest_dataset.cron_expr`（看板新鲜度标签的"应跑"来自它）、`automation/sourcing/task-progress-config.json`（"定时任务"卡片来自它）。改调度必须三处一起改，2026-10-04 就是发现推广采集只有第一份有、后两份空着才补上的（spec §35）。另外 `detect_alerts.py` 没有自己的 crontab 行——它由 `inventory_cron.sh` 链式调用，所以注册表写 `0 5 * * *` 是对的，别当成缺配。**这条对齐现在有门了**：`python3 scripts/check-consistency.py` 检查 A 会把四份副本按脚本名对齐（含 shell 链式展开），注册表有而机器上没有＝没人跑、时刻不一致、卡片没登记都报失败。
- **生意参谋的访客数不能直接用，先剔异常流量**：判据 `visitors >= 100 AND bounce_rate > 0.8 AND pay_byrs = 0`
  定义在 `DashboardMapper.ABNORMAL_TRAFFIC`，`ItemOpsMapper.xml` 的 `itemOpsBase` 里还有一份同文副本
  （Java 注解与 XML 两份，编译器管不到）。**改一处必须改另一处**，`ItemOpsParamTest` 会读 mapper 原文逐字比对，
  改坏了会报"两页按不同口径剔流量"。09-30 那次快照 14,966 访客里 14,365 是 16 件这种商品贡献的（跳失 97%~99%、
  零加购零成交），正常商品平均只有 3.2 访客。新增 sycm 消费方时沿用这个判据，别另起一套（spec §38，前因见 §34）。
- **剔除量必须和它解释的那个访客数出自同一份快照**：`DashboardKpiVo.abnormalItems/abnormalVisitors` 由 `DashboardServiceImpl` 从 `latest`（= `snapshots.get(0)`，SQL 是 `ORDER BY snapshot_time DESC`）一起带出来，首页那句"访客数已剔除 N 个…"读的是 kpi。
  **别改成按下标从趋势数组里取**：接口给前端的趋势数组是 ASC（旧→新），下标 0 是最老那天——2026-10-06 就是这么写的，异常恰好为 0 才没露馅，而 10-02 那天最新快照剔了 16 件 / 14,365 访客，界面会说"访客 616，已剔除 0"。同理 `Result` 里 `code 9999 您的网络有问题请稍后重试` 也可能是**调用方用错方法**（GET 接口被 POST 打），先看日志里的异常名再决定改哪边。
- 根 pom 的 `<spring-boot.version>3.4.0</spring-boot.version>` 是**死属性**（无任何引用），实际生效的是 parent 3.3.5；升级版本改 parent 那行，勿被它误导。
- `GlobalExceptionHandler` 把"调用方用错接口"的五类（缺必填参数 / 参数类型不对 / 请求体不是合法 JSON / 路径不存在 / **HTTP 方法用错**）单独收成 `code 400` + 人话原因，不再统统走 catch-all 的 `9999 您的网络有问题请稍后重试`——那类以前还会落一条 ERROR 全栈，把"后端日志 0 ERROR"这条健康判据冲淡。方法用错是 2026-10-06 补的第五类：`@GetMapping("/menus")` 被 POST 打时回的就是 9999，我据此误判过"后端坏了"。为此 `common-service/pom.xml` 显式加了 `spring-boot-starter-web`（provided）：`MissingServletRequestParameterException` 的父类在 `jakarta.servlet` 里，不加编译不过（common-util 那份是 provided，不传递）。**回显文案一律自己拼，别打 `e.getMessage()`**：坏 JSON 的 message 里带着请求体原文。见 spec §32

## 登录拦截白名单

`common-util/.../utils/Constant.java` 的 `whiteList`：登录/微信 mock 路径、静态资源、swagger（`/doc.html`、`/v3/**`）。要放行新路径改这里，勿在拦截器里硬编码。

## 业务域（service/ 包）

| 包 | 用途 |
|----|------|
| `expense` | 对账管理：支付宝 CSV 幂等导入、打标规则引擎、月末关账 |
| `ingest` | 采集契约/新鲜度：`ingest_dataset` 判据 + 过期告警写 `sync_alert`（调度在系统 cron / LaunchAgent，后端只判定）。**`sync_alert` 两个独立标志**：`status`（0 未读 / 1 已读 / 2 已自动解决）是产品语义，`notified`（0/1）只表示"有没有推给外部 IM"——没配 `spzx.alert.dingtalk-webhook` 时 `notified` 恒 0，**那不是积压**，别拿它当"告警丢了 N 条"汇报。未读的出口是应用内三处：顶栏「待处理提醒 N」badge（`AlertBell.vue`，60s 轮询 `/admin/syncAlert/count` + 路由变化即刷）、首页未读卡、任务进度页的列表与"全部标记已读"。owner 明确不要外部 IM 推送。 |
| `kw` | AI 选词推广：引擎凭据在 DB `kw_provider` 表 + `application-local.yml`；`KwAutoRunTask` 默认关闭。**关键词出价计算器** `POST /admin/kw/bid/calc`（纯算术、不碰库、不花钱）：链条 `关键词出价 ×(1+人群溢价) ×分时折扣`，全能调价只按公布的幅度给**区间**（平台黑箱，反推一律用最坏情况 +幅度），人群命中多个人群**取最高溢价不相加**；反推口径两种（按可承受推广费率 / 按每单毛利分成），可直接带商品运营台一行（客单价取**成交均价** = 成交额/买家数，不是标价；`abnormalTraffic=1` 的宝贝拒绝带入）。公式与校验全在 `KwBidCalculator`（18 条单测），页面 `/#/kwBidCalc` 只渲染不自己算 —— 别把公式抄第二份。**页面按"简单+横排+等式即表单"定过型（2026-10-06）：一张卡里把整条链条写成一行——`关键词出价 ×（1+人群溢价[输入]）× 分时折扣[输入] ×（1+全能调价[输入]）= 实际出价[输入]`。等号右边叫**实际出价**（不叫"行业平均出价"——那是常填进来的一个参考值，owner 纠正过），接口字段同步改成 `actualBid`（原 `marketAvgBid`），响应回 `solvedFrom` 说明这次解的是哪一头。**等式双向、但一次只解一头**：`solved='baseBid'` 填实际出价→左边回填 `recommendedBaseBid`；`solved='actualBid'` 填关键词出价→右边回填 `cells[0].high`；两头都不给→400。判据行读后端 `goalGap`/`ceilingGap` 的**正负**（正＝还留余地，负＝已顶破目标/每次点击上限），前端不自己乘一遍比大小。**"等式必须成立"优先于"框里是安全值"**：勾利润后建议值（`adviceBaseBid`，两条约束取最小）写在旁边文案里而不是直接填进左框——直接填会让 `0.24 ×2 = 1.20` 这种假等式出现在屏上（owner 第四次反馈就是这个）；点"填建议值"才写进左框，并同时把方向翻成 `actualBid`，让右边跟着重算成 0.48。勾了利润出现第二行 `客单价 × 转化率 × 费率 = 每次点击最多值 → 按利润这一栏最多填`。别写成连除、别做成左右两栏表单（owner 连着四次说"公式错了/横着展示/要灵活"，第二次那次其实公式没错，错在屏上写成 `÷÷÷` 且把目标放在等号左边）。**差额用 `signedMoney` 不用 `money`**：后者按"上限"设计拒绝负数，把超均价的负差喂进去会 400"金额不能为负数"（本轮踩过，是单测抓出来的）**；接口侧仍支持但页面不再暴露的维度有：对标系数 `targetPct`、按毛利分成、带商品运营台一行（`target.item`，客单价取**成交均价** = 成交额/买家数，`abnormalTraffic=1` 的宝贝拒绝带入）、多人群×多时段矩阵（`cells`，页面只渲染第一档）。往这个页面加东西前先想到 owner 说过三次的"不要搞得那么复杂" |
| `platform` | 平台/店铺/能力只读注册表（`PlatformRegistryService`），P0 直查库不缓存。`shop.cdp_port` 是**机器端口的镜像**（淘宝 9222 / 抖音 9223 / 拼多多 9224），权威值在 `automation/{tb-auto,sourcing,pdd-auto}` 的 config 里，改端口以 config 为准再同步这张表；`multiplatform_p0_seed.sql` 已改成**不再覆盖 `shop.status`**（拼多多店运营中已=1，重跑种子会把这家停用） |
| `promo` | 推广日报：主路是 `automation/tb-auto/collect_alimama_promo.py` 直连万相台报表接口采集（LaunchAgent 每日 22:00）；`/admin/promo/import` 的 CSV 导入是兜底路，列名映射存 DB `promo_import_map`（当数据不当代码，全部 `verified=0` 未跟真实导出对过）；看板读接口 `/admin/promo/report/{summary,trend,plans,items,facetCounts}` 纯只读（前端 运营 > 推广日报）；比率一律用汇总后的分子分母重算，分母为 0 出 NULL 不出 0；宝贝页另有 进价/运费/净利 三列，**净利不含运费**（与 `itemOpsBase` 的 margin 同一口径，全库 4683 个商品只有 17 个有非零运费），且**不建利润汇总表**——225 行现算 0.12s，物化只会换来滞后。见 spec §30 |
| `videogen` | 火山方舟 Seedance 视频生成（`ArkVideoClient` + `VideoPricing` 计费护栏 + 启动对账 `VideoGenStartupReconciler`） |
| （无 `novel` 子包） | 小说/番茄逻辑在 service/ 顶层：`NovelService`、`NovelChapterService`、`FanqiePublishService` |

平台级业务细节/运营红线见全局 `~/.config/opencode/AGENTS.md`。

## 文档 / 杂项

- **`docs/ECOMMERCE_RULES.md`：国内多平台运营规则备忘（拼多多/淘宝/抖店/1688）** —— 平台品牌管控触发词、
  划线价合规条款原文、费率基准、定价真实口径、"哪些还 unknown"。**碰任何上架/定价/标题清洗前先读它**；
  学到新规则（尤其被平台驳回/处罚出来的）就往里加，必须带出处或实测样本，没核实的写 §7 待核实。
- `docs/DEVELOPMENT.md`（开发文档）；`docs/ARCHITECTURE.md`（微服务蓝图，未落地）
- `docs/superpowers/`：功能交付台账（`specs/`+`plans/`+`audits/`）。2026-09-30 两份 PDD 设计（`pdd-wearable-nail-distribution`、`pdd-1688-product-binding`）**状态待评审、后端/前端未落地**，别按文档找 Java 代码。
- `spzx-manager/src/main/resources/sql/db_optimization_plan.sql`：索引优化方案（执行前审阅）
- 远程：GitHub `qyongkai9527/spzx-parent`

## automation/ — Python 电商自动化生态（sourcing/tb-auto/fanqie-publish 于 2026-09-23 从 `~/` 迁入；pdd-auto 2026-09-30 新建）

Playwright async + CDP。Python 3.9，统一 `automation/venv/bin/python`。**Chrome 风控红线 / CDP 端口分工 / cron / 小说发布闭环见全局 `~/.config/opencode/AGENTS.md`；逐目录坑位见 `automation/{sourcing,tb-auto,pdd-auto}/AGENTS.md`。**

| 子目录 | 用途 | CDP |
|---|---|---|
| `automation/sourcing/` | 1688 选品/归类调价/抖店直建 | 9223 |
| `automation/tb-auto/` | 1688→淘宝铺货/巡检/小说章节导入 | 9222 |
| `automation/fanqie-publish/` | 番茄小说自动发布（常驻 publish_auto.py，每日 12:00 发 8 章） | 9223 |
| `automation/pdd-auto/` | 淘宝穿戴甲→拼多多铺货（1688 直铺，`run_pdd_1688.sh` 循环） | 9224（发布，窗口模式）；采集复用 9222 |

- pdd-auto 是**第四条线**：CDP 9224 独立 profile，提交类必须窗口模式（PDD 发布入口是 `/goods/category` 不是 `/goods/publish`）；主图须缩到 1080px 否则商详校验静默拦截。细节见 `automation/pdd-auto/AGENTS.md`。
- 数据/缓存/登录态（chrome-profile*、*.jsonl、novel_batches、xlsx/mp4、pdd_images* 等）已 gitignore，勿提交；**别直接 `git add -A`**——2026-10-03 一次 `-A` 把 `pdd_images` 下 3003 张 jpg 全吞进对象库（741MB），`.gitignore` 现按 `automation/**/*.{jpg,jpeg,png}` 兜底
- 代码中出现 `/Users/qyk9527/sourcing|tb-auto|fanqie-publish` 旧路径 = bug（yml/@Value 曾漏改 10 处，2026-09-24 已全部修复）
