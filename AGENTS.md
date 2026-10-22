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
- 脚本启动那份后端（`java -jar`）把 pid 记在 `~/Library/Application Support/spzx-local/pids`，双击桌面开关即停。实测对照：老 `spring-boot:run` 那份 footprint 579MB / 56 线程 / 空闲 4.4%、还多挂一个 765MB 的 maven 父进程；脚本这份 282–310MB / 34 线程 / 空闲 0.2%、`Started ManagerApplication in 4.4s`。改完 Java 代码：端口空着脚本自己重新打包再起；端口被别的会话用 `target/classes` 占了，那份得在它自己的启动方式里重启，脚本管不到。**别假设它一定在跑**：`pids` 为空、或 `curl -m3 -o /dev/null -w '%{http_code}' localhost:8501/` 回 `000` 就是没起（2026-10-12 实测即此状态）。

**无 CI、无 mvnw、无 lint/format 工具链**——验证只能本地跑：`mvn compile` + `mvn test -Dtest=…` + **`python3 scripts/check-consistency.py`**（一致性门：调度四份副本 / 前端调用点 vs 后端路由（2026-10-10 实测 221/258；以命令输出为准） / 判据副本，退出码非 0 就是漂移；先 `--selftest` 证明它报得出红，再信它的绿。改 cron/LaunchAgent/注册表/卡片配置、加或删 controller 端点、动异常流量判据，都要跑它）。

## 测试

- `spzx-manager` 下 24 个测试类（`find spzx-manager/src/test -name '*Test.java' | wc -l`），**除 `EmailTest` 外全是纯 JUnit 单测**（不联网、不拉 Spring 上下文，覆盖 expense/kw/videogen/ingest/platform/promo/dashboard/itemops 等）。单跑：
  `mvn test -pl spzx-manager -Dtest=AlipayBillCsvParserTest`
- `EmailTest` 是 `@SpringBootTest`，需 MySQL/Redis 在线；**裸 `mvn test` 会带上它**——环境不全必挂，单测一律用 `-Dtest=` 指定。
- **跑单测必须带 `-am`**：`mvn test -pl spzx-manager -am -Dtest='!EmailTest' -Dsurefire.failIfNoSpecifiedTests=false`（2026-10-07 实测：不带 `-am` 时 `GlobalExceptionHandlerReasonTest` 有 2 条红，源码与 HEAD 逐字一致却测不过——因为 `spzx-common/*` 用的是 `~/.m2` 里**别人那次 install 的旧 jar**。不带 `-am` 的红绿都不作数。`-Dtest=!EmailTest` 是排掉那个要连库的；加了 `-am` 后公共模块没有匹配测试，还要带 `-Dsurefire.failIfNoSpecifiedTests=false`，否则 common-util 那步直接 BUILD FAILURE。）
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

- MySQL `localhost:3306/db_spzx`（用户 root，**口令不在仓库里**：真值在 gitignore 的 `application-local.yml`，`scripts/mysql-cnf.py` 由它生成 `~/.spzx/db.cnf` + `/tmp/spzx_my.cnf` 两份 600 文件；Python 侧统一 `automation/sourcing/dbconf.py` 读，不再各写一份）、Redis `localhost:6379`（无密码）——宿主机直装，**而且两个都开机自启**（本文档此前写"机器重启后不自启"是错的。2026-10-08 实测：`kern.boottime` = 10-02 21:28:34，mysqld 21:28:45 起、redis-server 21:29:01 起，都跟着开机；MySQL 由 `/Library/LaunchDaemons/com.oracle.oss.mysql.mysqld.plist`，Redis 由 `~/Library/LaunchAgents/homebrew.mxcl.redis.plist`，两份 `RunAtLoad` 都是 true，Homebrew 那份还带 `KeepAlive`）。
  命令行连库一律 `mysql --defaults-extra-file=/tmp/spzx_my.cnf`，**别把口令写进命令行**；这个文件会被 macOS 清 /tmp 清掉，重建：`python3 scripts/mysql-cnf.py`（口令按 环境变量 `SPRING_DATASOURCE_PASSWORD` → `application-local.yml` → dev.yml 旧明文 的顺序找，一次写两份 600 文件，`--test` 顺手连一次）。带中文的 SQL 靠它里面的 `default-character-set=utf8mb4` 才不会双重编码。**automation 下的 Python 一律 `from dbconf import DB_CONFIG`（跨目录脚本先按既有约定把 `automation/sourcing` 加进 `sys.path`）**，不要再写自己的 `DB_CONFIG`；`dbconf.py` 的搜索顺序是 `SPZX_MYSQL_CNF` → `~/.spzx/db.cnf`（重启还在）→ `/tmp/spzx_my.cnf`。口令回潮由 `check-consistency.py` 检查 E 报红（它扫的是 git 已跟踪的代码/配置文件，`application-local.yml` 被 ignore 所以不算）。历史交付台账（`docs/superpowers/`、`.superpowers/`）里的明文**没动也不该动**——真要断根是换口令。
- Redis `localhost:6379`（无密码，Homebrew 8.8.0）**别当 spzx 的附属服务随手停**：这台 6379 是全机共用的——实测同时挂着本机另外几个 Java 项目的连接，db0/db1/db9 里的键（2026-10-08 16:15 实测 1007 个）全是 `auth:refresh_token:*` / `prefix_user_token_*` 这类登录令牌，而内存只占 2.8M，停它省不出什么。起停走 `scripts/start-redis.sh|stop-redis.sh`（桌面 `~/Desktop/Redis开关.command` 双击切换），判据是 `redis-cli ping` 回 PONG 而不是"端口在听"。语义按 `brew services --help` 原文：**stop = 立刻停 + 注销开机/登录自启**、**start = 立刻起 + 注册自启**、**kill = 只停但保留注册**——这份 plist 带 `KeepAlive=true`，所以 `kill`／`redis-cli shutdown` 都会被 launchd 原地复活，停必须用 `stop`。stop-redis.sh 因此在动手前列出"停了会打断谁"并要一句确认（非 tty 环境不加 `--yes` 就直接拒绝），停完再等 3 秒复查端口有没有被复活。判据夹具 `scripts/test-redis-toggle.sh`（9 项，其中"发了 start 却不应答＝失败"和"杀了又起来＝没停住"两盏红灯是特意跑出来的）在 6399 的独立沙盒实例上跑，全程不碰 6379；**真服务上那一次 stop 还没实跑过**（它会让 6379 断几秒、打断另外两个项目的连接），要做需要单独点头。
- **库有备份了（2026-10-08 起；2026-10-19 并入 db_daily）**：每天 **04:30** 由 `scripts/db_daily.sh` 第1-2步跑 `scripts/backup-db.sh && scripts/verify-restore.sh`（原独立 LaunchAgent `com.spzx.db-backup` 已从机器撤下，仓库副本 `scripts/launchd/` 留档）——先全量 `mysqldump`（41.8MB 逻辑库 → gz 约 4MB，3 秒）落到**仓库外**的 `~/Backups/spzx-db/`（日份留 7 天 + `weekly/` 留 8 周），**再立刻把这份 dump 还原进临时库 `spzx_restore_probe` 验一遍**（6 秒）。只 dump 不验的备份等于没备份。判据四条：表数==**真库**表数、缺表清单为空、锚点表行数一致、按中文关键词查得到内容——第四条是因为历史上栽过字符集二次编码。两条踩过的坑：① `mysqldump` 不认 cnf 里的 `database=` 键（unknown variable），脚本从现成 cnf 现场剔掉再生成 600 的临时文件；② **故意不带 `--databases`**：带了就会在产物里写 `DROP DATABASE IF EXISTS db_spzx`，那这份"顺手管道进 mysql 就把生产库删了"的文件不该当天顶备份，恢复到哪个库由 `-D` 指定。校验侧也钉了红线：临时库名不许以 `db_` 开头、建之前必须不存在、只 DROP 本次亲手建的那个。验货方式不是"它报绿"——拿一份**被删掉 41 张表**的 dump 去跑，它必须报红（第一版真的报的是"表数一致 71/71，可以恢复"，判据因此改成对真库的表清单而不只是对 dump 自己的条数；`q()` 吞错误返回空串也会判 -1 红，否则"表整个丢了"会显示成一句半话）。**已收口**：机器睡着/关机那晚备份会不会被跳过，由 `daily_schedule.py` 的第七类事实（当天的备份产物文件）兜住（早于 `BACKUP_SINCE=2026-10-08` 的日子不判定）。口令依旧只走 extra-file，不进命令行、不进仓库。
- `spring.config.import: optional:classpath:application-local.yml` — 本地覆盖文件已 gitignore，**密钥/凭据放这里，勿提交**。dev.yml 里 `datasource.password` 只剩 `${SPRING_DATASOURCE_PASSWORD:}`。
- 微信扫码登录 `wx.login.mock-mode: true`：dev 登录走 mock（白名单含 mockScan/mockConfirm），无需真实微信回调。
- MinIO `127.0.0.1:9000`（minioadmin/minioadmin），bucket `spzx-manager`。
- `spzx-manager` 资源 `filtering=true`：resources 里的 `${...}` 会被 Maven 构建期替换，勿把运行期占位符写进 yml。**但带默认值的 Spring 占位符活得下来**：`filtering` 只替换它认得的 Maven 属性，`${SPRING_DATASOURCE_PASSWORD:}` 原样进包（2026-10-07 实测：`unzip -p target/spzx-manager.jar BOOT-INF/classes/application-dev.yml` 里那行没被吃掉，重启后读库接口正常）。写别的 `${x}` 前先想这条。
- ES / ClickHouse：仅 pom 引入依赖，**无任何配置与代码引用，未启用**（yml 的 `app.enable-infra` 开关也无代码绑定）；**没有 RocketMQ**（依赖都没有）。
- dev 开了 `spring.main.lazy-initialization: true`：缺 bean / 配置错误会延迟到首次调用才爆，别只看启动日志判断健康。**但 `@Scheduled` 不需要 `@Lazy(false)` 也会被调度**——本文档此前写的"不加就永不调度"已于 2026-10-03 被日志推翻：`QrLoginTicketCleanTask` 没有该注解，进程 22:00:02 启动、期间零 HTTP 请求，仍从 22:05 起每 5 分钟准点触发（共 59 次）。Boot 3.3.5 会把带 `@Scheduled` 的 bean 排除在懒初始化之外；`IngestFreshnessTask` 等三处现存的 `@Lazy(false)` 是显式保险，不是必要条件。另：devtools 热重启有时会撞上 maven 正在写 `target/classes`，日志里留下一条 `ERROR SpringApplication : Application run failed`（bean 创建失败），几秒后自动重试就 `Started ManagerApplication` 成功——**数 ERROR 做健康判据时要先看这条是不是已自愈**（2026-10-05 01:53 实测：19 秒失败、25 秒成功、端口 8501 一直在听）。
- `task-progress.config-path`、`visual.python-bin/script-dir` 硬编码本机绝对路径指向 `automation/`，仓库搬家即失效。**2026-10-07 主图质量分链路已修通**：`assess_visual.py` / `assess_main_img.py` / `generate_main_img_variants.py` 从 `_archive_20260906/` 移回 `automation/sourcing/`（后端按 `visual.script-dir` 找它们）；真正的断点不是路径而是 **venv 架构**——`automation/venv` 整批 C 扩展是 x86_64（Rosetta 时代建的），而 cron/后端按 arm64 调它，纯 Python 脚本照常跑、`import numpy/PIL.Image` 一律炸（numpy 降到 1.26.4、Pillow 重装成 arm64 才通；`av`/`tokenizers`/`hf_xet` 仍是 x86_64 但没有任何现役脚本用）。**`product_media.update_time` 是普通 datetime 没有 `ON UPDATE CURRENT_TIMESTAMP`**（`source_product.update_time` 有），所以脚本 UPDATE 必须显式 `update_time=NOW()`，否则质量分页的「分数截至」（读 `max(product_media.update_time)`）永远停在旧批次不前进。全量重跑没做：`assess_main_img.py` 不带参数是 18796 行、逐行下载 alicdn 图，属大批量外网访问，要跑先限量分轮。变体图库里存的是本机绝对路径（生成脚本没传 MinIO），浏览器加载不了，页面只显示文件名。见 spec §31
- **plist 现在在仓库里有副本**：`scripts/launchd/com.spzx.*.plist`。以前只有 `~/Library/LaunchAgents/` 那一份，2026-10-08 我亲手验证了这个单点有多脆：用 `plutil -extract StartCalendarInterval json <file>` 想"读一下钟点"，**这个命令不带 `-o -` 就是原地覆写文件**，两份在跑的作业定义被换成了 22 字节的 `{"Hour":22,"Minute":0}`——作业当下还在内存里（`launchctl list` 照旧绿），重启机才会发现没人跑了。恢复靠 `launchctl print gui/$(id -u)/<label>` 打出的内存定义逐项抄回，改完必须 `plutil -lint` + `bootout`/`bootstrap` 重载 + 再 `launchctl print` 对字段。所以：**读 plist 用 `plutil -extract … -o -`，或直接用 `PlistBuddy -c Print`**；改完记得同步 `scripts/launchd/` 那份副本（`cmp` 逐个核）。同一轮还顺手发现 `check-consistency.py` 的 FLOOR `secret_scanned` 数的是 `git ls-files`（含**已 staged** 的文件），别的会话暂存十几个代码文件就能让这道门自己翻红或翻绿——它不是稳定判据，待收口。
- **`scripts/launchd/` 里还有两条「一次性窗口」作业**：`com.spzx.tb-pdd-window-{start,stop}`（`StartCalendarInterval` 写死 `Month=10/Day=10`，只在 2026-10-10 触发过；2026-10-12 复核已从 `~/Library/LaunchAgents/` 撤下，仓库副本仍留在这儿），跑 `scripts/window-run.sh`——9222 窗口 Chrome + PDD 全程并行 + 归类 v2→品牌串行，到点由 `window-stop.sh` 收场。⚠️ `window-run.sh` 里的脚本名是**故意拼接**的（`W_CAT=run_cat_v2` / `W_PDD=run_pdd_1688`），不写字面 `*.py/*.sh` 以免被 `check-consistency.py` 的 `cron_targets` 当成"这作业会跑那些脚本"制造假漂移——别把它"修"成字面名。
- **加定时作业别用 `crontab <文件>` 写**：这台机器上从 CLI 装 crontab 会挂死等一个不弹出来的授权框（2026-10-07 实测：`crontab -` 与 `crontab 文件` 都卡满超时，`crontab -l` 却正常）。走 `~/Library/LaunchAgents/com.spzx.*.plist` + `launchctl bootstrap gui/$(id -u) <plist>`，`launchctl kickstart -k gui/$(id -u)/<label>` 立刻试跑一次，日志看 plist 里的 `StandardOutPath`。
- **每天 23:30 有一份作业把当天事实写进后台「日程管理」**（`scripts/daily_schedule.py`，LaunchAgent `com.spzx.daily-schedule`，注册表 code `daily_schedule`）：七类事实 = `ingest_batch` 跑批（轮次/成功/少一批/失败 + 读落库行数）、`sync_alert` 新增告警、`platform_product` 商品登记、`product_media`/`source_product` 当日质量分、`novel_chapter.published_at`、两个仓库的 `git log`、**`~/Backups/spzx-db/` 里当天的备份文件**（第七类，2026-10-08 加：备份产物在仓库外、库里不记行，所以只能看文件；早于 `BACKUP_SINCE=2026-10-08` 的日子不判定，免得把没装备份的历史诬成"漏备份"）。脚本条目 `create_by=0`，重跑同一天只删自己写的（人工在页面上加的任务不动）；`--days 3` 让晚到的事实第二天自愈。完成判定来自事实（有 failed/partial、还有未读告警＝未完成），不粉饰。**`sys_user_schedule.task_count/complete_count` 有三处算法**：`daily_schedule.py`、`log_work.py` 里的 SQL 与 `SysUserScheduleTaskServiceImpl.updateCompleteValue`，改口径要一起改。手工导入（对账/推广 CSV）不进 `ingest_batch`，所以不进日程——别把这里的条数当成当日全部工作量。
- **每完成一件活就留痕**（`scripts/log_work.py`，2026-10-08 交付，spec `docs/superpowers/specs/2026-10-08-work-log-schedule-design.md`）：一件活收尾（或长任务告一段落）**立即**记进当天日程，别等 23:30——手做的自动化活（归类 v2/品牌/PDD/选品/AI 选词/图片/手工导入）不进 `ingest_batch`，没 commit 就永远不进 `daily_schedule.py` 的七类事实。写 `create_by=-1`（哨兵「AI/手工代记」）故 **23:30 的 `DELETE ... create_by=0` 删不到它**；手动页面上加的是用户 id(≥1)，自动台账是 0。`--progress-file <json>` 自动解析（顶层 dict 里 list/dict 键取 `len()`，如 `done 1464 / skipped 1339 / failed 1079`）、`--progress` 手填；长任务用 `--merge` 按「同一天+模块+标题」原地刷新（不堆行），零散小活用默认追加保留时间线。**模块用自由文本**，建议清单：淘宝归类、品牌标题、PDD铺货、1688选品、AI选词、视频生成、对账、小说、系统、其它（不强制）。`sort` 走 1000+ 段排在自动条目后；**不写 `ingest_batch`、不注册 `ingest_dataset`**（免得污染「应跑」口径）。`daily_schedule.py` 的父表 `remark` 已改成按全量 `status=0` 行重算，与 `task_count` 同口径。
- **"这个作业几点跑"有三处来源**（`check-consistency.py` 把 `crontab` 与 LaunchAgents 拆成两份来核，故门里称"四份副本"）：机器上的 `crontab -l` / `~/Library/LaunchAgents/*.plist`（推广采集是 launchd 的 `com.spzx.alimama-promo`，每日 12:06，**不在 crontab 里**）、注册表 `ingest_dataset.cron_expr`（看板新鲜度标签的"应跑"来自它）、`automation/sourcing/task-progress-config.json`（"定时任务"卡片来自它）。改调度必须三处一起改，2026-10-04 就是发现推广采集只有第一份有、后两份空着才补上的（spec §35）。另外 `detect_alerts.py` 没有自己的 crontab 行——它由 `db_daily.sh` 第3步经 `inventory_cron.sh pool` 链式调用（04:30），注册表写 `30 4 * * *` 是对的，别当成缺配。**这条对齐现在有门了**：`python3 scripts/check-consistency.py` 检查 A 会把四份副本按脚本名对齐（含 shell 链式展开），注册表有而机器上没有＝没人跑、时刻不一致、卡片没登记都报失败。
- **生意参谋的访客数不能直接用，先剔异常流量**：判据 `visitors >= 100 AND bounce_rate > 0.8 AND pay_byrs = 0`
  定义在 `DashboardMapper.ABNORMAL_TRAFFIC`，`ItemOpsMapper.xml` 的 `itemOpsBase` 里还有一份同文副本
  （Java 注解与 XML 两份，编译器管不到）。**改一处必须改另一处**，`ItemOpsParamTest` 会读 mapper 原文逐字比对，
  改坏了会报"两页按不同口径剔流量"。09-30 那次快照 14,966 访客里 14,365 是 16 件这种商品贡献的（跳失 97%~99%、
  零加购零成交），正常商品平均只有 3.2 访客。新增 sycm 消费方时沿用这个判据，别另起一套（spec §38，前因见 §34）。
- **剔除量必须和它解释的那个访客数出自同一份快照**：`DashboardKpiVo.abnormalItems/abnormalVisitors` 由 `DashboardServiceImpl` 从 `latest`（= `snapshots.get(0)`，SQL 是 `ORDER BY snapshot_time DESC`）一起带出来，首页那句"访客数已剔除 N 个…"读的是 kpi。
  **别改成按下标从趋势数组里取**：接口给前端的趋势数组是 ASC（旧→新），下标 0 是最老那天——2026-10-06 就是这么写的，异常恰好为 0 才没露馅，而 10-02 那天最新快照剔了 16 件 / 14,365 访客，界面会说"访客 616，已剔除 0"。同理 `Result` 里 `code 9999 您的网络有问题请稍后重试` 也可能是**调用方用错方法**（GET 接口被 POST 打），先看日志里的异常名再决定改哪边。
- 根 pom **两个死属性**：`<spring-boot.version>3.4.0`（无任何引用，实际生效的是 parent 3.3.5，升级版本改 parent 那行）与 `<mysql.verison>8.0.30`（连拼写都错、也无引用；真实驱动版本在 `dependencyManagement` = `mysql-connector-java 8.0.33`）。**`dependencyManagement` 里钉的 `commons-compress 1.25.0` 别删**：POI 5.2.5 / easyexcel 4.0.3 需要 ≥1.25.0 的 `putArchiveEntry(ZipArchiveEntry)`，而 minio 8.5.2 会传递 1.21 → 删了就是运行期 `NoSuchMethodError`。`fastjson 2.0.65`、`lombok 1.18.34` 同在此统一版本。
- `GlobalExceptionHandler` 把"调用方用错接口"的五类（缺必填参数 / 参数类型不对 / 请求体不是合法 JSON / 路径不存在 / **HTTP 方法用错**）单独收成 `code 400` + 人话原因，不再统统走 catch-all 的 `9999 您的网络有问题请稍后重试`——那类以前还会落一条 ERROR 全栈，把"后端日志 0 ERROR"这条健康判据冲淡。方法用错是 2026-10-06 补的第五类：`@GetMapping("/menus")` 被 POST 打时回的就是 9999，我据此误判过"后端坏了"。为此 `common-service/pom.xml` 显式加了 `spring-boot-starter-web`（provided）：`MissingServletRequestParameterException` 的父类在 `jakarta.servlet` 里，不加编译不过（common-util 那份是 provided，不传递）。**回显文案一律自己拼，别打 `e.getMessage()`**：坏 JSON 的 message 里带着请求体原文。见 spec §32

## 登录拦截白名单

`common-util/.../utils/Constant.java` 的 `whiteList`：登录/微信 mock 路径、静态资源、swagger（`/doc.html`、`/v3/**`）。要放行新路径改这里，勿在拦截器里硬编码。

## 定时任务时刻表（2026-10-19「方案A」起）

**写任务只在夜窗，中午窗口全程只读**；ISV 库存同步是唯一日常写淘宝的定时作业。时刻四份副本对齐规则见上节，改完必跑 `check-consistency.py`。

| 时刻 | 作业 | 载体 |
|---|---|---|
| 03:00（jitter≤5min） | 夜窗链 `automation/sourcing/run_night_window.sh` 串行三段：夜巡(detect_stock_change `--tiered`) → ISV库存同步(成功后自动接 `isv_sync_verify` 抽查) → 收9222；任一段失败不拦后段 | launchd `com.spzx.stock-refresh` |
| 04:30 | `scripts/db_daily.sh`：备份→还原验证→告警检测(`inventory_cron.sh pool`)→质量分级→`cleanup_runtime.sh`，全程不碰 Chrome（原 04:10 备份/05:00 inventory_cron/05:30 分级三个独立调度已并入） | crontab `30 4` |
| 12:06→12:35→12:50→13:10 | 中午只读窗口：alimama日报 → 生意参谋商品快照(crontab) → 在售扫描 → 收9222（`chrome_kill.sh` 有 BUSY 守卫，任务在跑就放过） | launchd ×3 + crontab `35 12` |
| 19:30 | 事件驱动 `run_stock_event_sync.sh`：`stock_event_check.py` 判定「4类白名单告警(isv_sync_fail/source_dead/onsale_binding_change/onsale_mismatch)当天新写且未读 ∪ 今日无 isv_stock_sync success 批次」才拉9222补跑同步；无事件一行日志退出、**不写台账**——新鲜度面板当天没有 19:30 批次属预期，不是漏跑（low_stock/oversell_risk 被 owner 移出事件集） | launchd `com.spzx.stock-sync` |
| 23:30 / 每小时 | `daily_schedule.py` 写日程台账 / `task_stats.py` 刷看板统计 | launchd / crontab `0 *` |

- 周六 1688详情采集合并已退役、03:30 运费补抓已停用（2026-10-19 owner 定：省 9223 占用）；注册表 `source_freight=30 3 * * 6` 未删、卡片已降 manual，它的「应跑」别当真。
- **时刻表上的坑**：
  - **`isv-container` ≠ 抖店**：ISV 同步/在售扫描走的是**淘宝服务市场 ISV 应用**（`scrape_isv_offer_taobao.py`，9222，fuwu.work「已关联货源」/myseller.taobao.com）。报错「没找到 isv-container iframe（登录态掉了？）」= **淘宝侧**会话问题，别往抖店方向排查（2026-10-21 踩过）。
  - **淘宝会话分域且会连坐**：alimama.com 独立于 taobao.com（sycm/ISV 应用）。10-20 实证 12:06 alimama 重采后，12:35 sycm「未捕获数据接口响应」、12:50 起 ISV 页 iframe 全找不到、连败到次日——恢复 = 9222 重新登录淘宝一次，下一轮排班自愈，`cron_failed` 告警由下个 success 批次自动销案，无需手动补跑。
  - **夜窗链外层 rc 不可靠**：`run_night_window.sh` 记的「同步 rc=0」是包装脚本退出码（`run_stock_sync.sh` 内层失败也 exit 0）；日志行 `rows=` 读的是 `stock_sync_report.json`，失败轮不重置＝上轮残留。健康判据 = `ingest_batch` + `/tmp/stock_sync_cron.log` 里的「结束 rc=N」。
  - **新增看板卡片必须 `type: process_only`**（或给可用 `path`），否则每小时 `task_stats.py` 直接 KeyError 崩（10-19 实证，onsale_scan 卡）。

## 业务域（service/ 包）

| 包 | 用途 |
|----|------|
| `expense` | 对账管理：支付宝 CSV 幂等导入、打标规则引擎、月末关账 |
| `ingest` | 采集契约/新鲜度：`ingest_dataset` 判据 + 过期告警写 `sync_alert`（调度在系统 cron / LaunchAgent，后端只判定）。**`sync_alert` 两个独立标志**：`status`（0 未读 / 1 已读 / 2 已自动解决）是产品语义，`notified`（0/1）只表示"有没有推给外部 IM"——没配 `spzx.alert.dingtalk-webhook` 时 `notified` 恒 0，**那不是积压**，别拿它当"告警丢了 N 条"汇报。未读的出口是应用内三处：顶栏「待处理提醒 N」badge（`AlertBell.vue`，60s 轮询 `/admin/syncAlert/count` + 路由变化即刷）、首页未读卡、任务进度页的列表与"全部标记已读"。owner 明确不要外部 IM 推送。**三类行的销案路径不一样，别当一套**：`ingest_stale` 由本类按 `dataset_code` 在恢复新鲜时关；`cron_skipped`/`cron_failed`（`cron_alert.py` 写的）由 `closeResolvedJobAlerts` 按台账关——`cron_skipped` 之后有任意落库(含 partial)即销案，`cron_failed` 只认 success，且批次时刻必须**严格晚于**提醒本身（同一轮台账先写、提醒后写，用 ≥ 会让失败轮自己销案）。这要求每条 `cron_alert` 调用都带 `--dataset`（15 处调用由 `check-consistency.py` 检查 D 钉住；以前不带，10-02/10-03 那批提醒永远挂着，顶栏 badge 只会涨）。历史行用 `sql/cron_alert_dataset_backfill.sql` 补 code。**`source_dead`（2026-10-18 起，第四类）**：`automation/sourcing/detect_alerts.py` 的 `detect_source_dead` 写——货源整个失效(`source_status=0`)且有淘宝绑定→新增（按未读同类幂等去重）；货源复活(`source_status=1`)→**自动销案 status=2**（销案与新增同轮判定，已实测）；随 04:30 `db_daily.sh` 第3步（`inventory_cron.sh pool`）每天跑。 |
| `kw` | AI 选词推广：引擎凭据在 DB `kw_provider` 表 + `application-local.yml`；`KwAutoRunTask` 默认关闭。**关键词出价计算器** `POST /admin/kw/bid/calc`（纯算术、不碰库、不花钱）：链条 `关键词出价 ×(1+人群溢价) ×分时折扣`，全能调价只按公布的幅度给**区间**（平台黑箱，反推一律用最坏情况 +幅度），人群命中多个人群**取最高溢价不相加**；反推口径两种（按可承受推广费率 / 按每单毛利分成），可直接带商品运营台一行（客单价取**成交均价** = 成交额/买家数，不是标价；`abnormalTraffic=1` 的宝贝拒绝带入）。公式与校验全在 `KwBidCalculator`（18 条单测），页面 `/#/kwBidCalc` 只渲染不自己算 —— 别把公式抄第二份。**页面按"简单+横排+等式即表单"定过型（2026-10-06）：一张卡里把整条链条写成一行——`关键词出价 ×（1+人群溢价[输入]）× 分时折扣[输入] ×（1+全能调价[输入]）= 实际出价[输入]`。等号右边叫**实际出价**（不叫"行业平均出价"——那是常填进来的一个参考值，owner 纠正过），接口字段同步改成 `actualBid`（原 `marketAvgBid`），响应回 `solvedFrom` 说明这次解的是哪一头。**等式双向、但一次只解一头**：`solved='baseBid'` 填实际出价→左边回填 `recommendedBaseBid`；`solved='actualBid'` 填关键词出价→右边回填 `cells[0].high`；两头都不给→400。判据行读后端 `goalGap`/`ceilingGap` 的**正负**（正＝还留余地，负＝已顶破目标/每次点击上限），前端不自己乘一遍比大小。**"等式必须成立"优先于"框里是安全值"**：勾利润后建议值（`adviceBaseBid`，两条约束取最小）写在旁边文案里而不是直接填进左框——直接填会让 `0.24 ×2 = 1.20` 这种假等式出现在屏上（owner 第四次反馈就是这个）；点"填建议值"才写进左框，并同时把方向翻成 `actualBid`，让右边跟着重算成 0.48。勾了利润出现第二行 `客单价 × 转化率 × 费率 = 每次点击最多值 → 按利润这一栏最多填`。别写成连除、别做成左右两栏表单（owner 连着四次说"公式错了/横着展示/要灵活"，第二次那次其实公式没错，错在屏上写成 `÷÷÷` 且把目标放在等号左边）。**差额用 `signedMoney` 不用 `money`**：后者按"上限"设计拒绝负数，把超均价的负差喂进去会 400"金额不能为负数"（本轮踩过，是单测抓出来的）**；接口侧仍支持但页面不再暴露的维度有：对标系数 `targetPct`、按毛利分成、带商品运营台一行（`target.item`，客单价取**成交均价** = 成交额/买家数，`abnormalTraffic=1` 的宝贝拒绝带入）、多人群×多时段矩阵（`cells`，页面只渲染第一档）。往这个页面加东西前先想到 owner 说过三次的"不要搞得那么复杂" |
| `platform` | 平台/店铺/能力只读注册表（`PlatformRegistryService`），P0 直查库不缓存。`shop.cdp_port` 是**机器端口的镜像**（淘宝 9222 / 抖音 9223 / 拼多多 9224），权威值在 `automation/{tb-auto,sourcing,pdd-auto}` 的 config 里，改端口以 config 为准再同步这张表；`multiplatform_p0_seed.sql` 已改成**不再覆盖 `shop.status`**（拼多多店运营中已=1，重跑种子会把这家停用） |
| `promo` | 推广日报：主路是 `automation/tb-auto/collect_alimama_promo.py` 直连万相台报表接口采集（LaunchAgent 每日 12:06，2026-10-19 由 22:00 改进中午只读窗口首棒）；`/admin/promo/import` 的 CSV 导入是兜底路，列名映射存 DB `promo_import_map`（当数据不当代码，全部 `verified=0` 未跟真实导出对过）；看板读接口 `/admin/promo/report/{summary,trend,plans,items,facetCounts}` 纯只读（前端 运营 > 推广日报）；比率一律用汇总后的分子分母重算，分母为 0 出 NULL 不出 0；宝贝页另有 进价/运费/净利 三列，**净利不含运费**（与 `itemOpsBase` 的 margin 同一口径，全库 4683 个商品只有 17 个有非零运费），且**不建利润汇总表**——225 行现算 0.12s，物化只会换来滞后。见 spec §30。**推广计划主档 `promo_plan`（2026-10-08）**：计划元数据的权威录入处，自然键 `(platform_code, shop_id, campaign_id)`，效果数据仍只在 `promo_cost_*_daily`，两边按 `campaign_id` 对。三条口径：① **不建 计划↔宝贝 子表**——`promo_cost_item_daily` 已经逐日记着实际投放主体，再建一张就是第二个真相源；② **不存派生值**（最后有花费的日期、累计花费、ROI 一律读时算，存下来必然滞后而滞后的数字在界面上像事实）；③ `online_status` **允许 NULL 且含义是「未确认」**——采集侧只说"当天没有投放数据"，没花费≠停投，不许据此自动翻成 0，由人在后台确认；前端下拉里的 `-1` 是"只看未确认"的查询哨兵（Integer 参数区分不了"没传"和"传了 null"）。`sql/promo_plan.sql` 末尾的采集登记种子**幂等**（`source='collected'`，名称取最近一天，其余列一律留空等人填），别把它改成覆盖元数据字段。同一批删掉了六张上游壳 `sys_plan`/`sys_plan_product`/`keyword_plan_product`/`_word`/`_crowd`/`oper_promotion_plan`（删前实测全 0 行、无外键、无活引用；结构备份 `sql/dropped_plan_shells_20261008.sql`）——**别再去找它们的 Java 代码，本来就没有**。未决：采集器默认只收 `bidType=custom_bid`，非标准计划进不了后台，"计划都维护进来"因此还缺一大半 |
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

Playwright async + CDP。Python 3.9，统一 `automation/venv/bin/python`。**跨目录通用经验 + 快速命令见 `automation/AGENTS.md`；Chrome 风控红线 / CDP 端口分工见全局 `~/.config/opencode/AGENTS.md`；cron 见 `~/docs/cron.md`；小说发布闭环见 `~/docs/novel-writing.md`；逐目录坑位见 `automation/{sourcing,tb-auto,pdd-auto}/AGENTS.md`。**

| 子目录 | 用途 | CDP |
|---|---|---|
| `automation/sourcing/` | 1688 选品/归类调价/抖店直建；**另有淘宝侧定时任务**（夜巡/ISV库存同步/在售扫描/sycm，这些连 9222） | 9223（淘宝侧脚本连 9222） |
| `automation/tb-auto/` | 1688→淘宝铺货/巡检/小说章节导入 | 9222 |
| `automation/fanqie-publish/` | 番茄小说自动发布（常驻 publish_auto.py，每日 20:00 发 8 章，2026-10-19 由 12 点改） | 9223 |
| `automation/pdd-auto/` | 淘宝穿戴甲→拼多多铺货（1688 直铺，`run_pdd_1688.sh` 循环） | 9224（发布，窗口模式）；采集复用 9222 |

- pdd-auto 是**第四条线**：CDP 9224 独立 profile，提交类必须窗口模式（PDD 发布入口是 `/goods/category` 不是 `/goods/publish`）；主图须缩到 1080px 否则商详校验静默拦截。细节见 `automation/pdd-auto/AGENTS.md`。
- `automation/sourcing/edit_brand_title_batch.py`（2026-10-07）：淘宝「睡衣/家居服」店铺分类商品批量改品牌(瑰若)+AI导购标题+AI主标题，CDP **9222**。与归类 v2 **抢同一淘宝账号**，一次只能跑一个（用户定：先 v2 后品牌）；逐条坑位见 `automation/sourcing/AGENTS.md`。
- **两个淘宝写任务共同的墙 = 账号级 RGV587 节流**（归类 v2 / 品牌批处理）：实测每轮爆发约 22–35 件即被拦、冷却 2h，**≈10 件/小时封顶**；并把冷却阶梯拉回重来只会更慢（**别频繁手动重启 wrapper**——重置后 20m/40m 短冷却窗口常 0 产出）。`run_cat_v2.sh` 遇风控(exit 42)阶梯冷却自愈；遇 **CDP 掉线**（`Browser context management is not supported` = 长跑 target 耗尽）2026-10-08 起会自动重杀/重启 9222 再续（此前会 `exit code=1` 静默结束——曾停摆 9 小时）。
- **阿里妈妈关键词运维**（`automation/tb-auto/`，连 9222 窗口模式）：`collect_alimama_promo.py`（LaunchAgent 每日 12:06 采推广日报，中午只读窗口首棒）+ `adjust_alimama_bid.py`（按「手淘市场均价」批量改关键词出价，**出价=均价/((1+溢价%)×折扣%)**，与 `KwBidCalculator` 同口径）+ `add_alimama_keywords.py`（批量新增关键词）。两个写脚本可反复跑、断点续跑（报告 json 是唯一状态）、默认 `--dry-run`，写入要 `--apply`；**加词严禁「先删后加」**——2026-10-12 初版先删后加把 5 个单元删空（真金白银换的，已改成「先加成功再删」）。逐条坑位见 `automation/tb-auto/AGENTS.md`。
- 数据/缓存/登录态（chrome-profile*、*.jsonl、novel_batches、xlsx/mp4、pdd_images* 等）已 gitignore，勿提交；**别直接 `git add -A`**——2026-10-03 一次 `-A` 把 `pdd_images` 下 3003 张 jpg 全吞进对象库（741MB），`.gitignore` 现按 `automation/**/*.{jpg,jpeg,png}` 兜底
- 代码中出现 `/Users/qyk9527/sourcing|tb-auto|fanqie-publish` 旧路径 = bug（yml/@Value 曾漏改 10 处，2026-09-24 已全部修复）

## spzx-ai-brain（独立工程，AI 客服「AI 大脑」Phase A）

- 路径 `/Users/qyk9527/ideaProject/spzx-ai-brain`（spzx-parent 兄弟目录，独立 Maven 工程，Spring Boot 3.4.5 + Spring AI 1.0.x）。
- 端口 8600；库 `db_ai_brain`（MySQL 同实例）；口令/控制台 token 在 gitignore 的 `application-local.yml`。
- 构建：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`，`mvn -q spring-boot:run`。
- 试打台 UI：`console-ui/`（Vue3+Vite+ElementPlus），`npm run build` 产物进 `src/main/resources/static` 由 8600 同源伺服；dev 5175 代理 `/console`。
- 边界：Phase A 工具只读 mock；试打全链路沙盒、零外发（控制台路径本就不做外发；真实外发入口后续须过 `OutboundGuard` 短路）。
- spec/plan：`docs/superpowers/{specs,plans}/2026-10-09-ai-*`。
- 真实 provider 种子（2026-10-09 手工装）：`ai_provider` 里 `tokens-store`，`base_url=https://tokens.store`（**host-root，不带 `/v1`**，`SpringAiChatInvoker` 自己拼 `/v1/chat/completions`），`text_model=deepseek-v4.1-flash`（`db_spzx.kw_provider` 里 tokens-store 的 `deepseek-v4-flash` 实测被拒 403「暂未开放」，该账号可用模型是 `deepseek-v4.1-flash`）。apiKey 走 `INSERT ... SELECT` 从 `kw_provider` 抄，**绝不落仓库/日志**。
- 冒烟坑：RAG 默认阈值 `0.10`，短问句（如「什么时候发货？」）命中片段得分约 `0.03` 会被滤掉 → `sources=[]`（不是链路坏）。要看到来源需 `overrides.rag.threshold` 调低（0.01 时命中「发货时效」得 0.0313）或扩知识片段。
