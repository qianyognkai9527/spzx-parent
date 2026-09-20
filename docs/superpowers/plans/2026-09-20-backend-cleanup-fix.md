# 后端全仓质量大扫除 · 修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。每个任务=一个批次，实现者以**审查报告为需求源**（含 path:line/修法/预估）。

**Goal:** 按审查报告执行批1-批4 修复，零预期行为变更（批2 为修 bug 的行为修正）。

**需求源:** `docs/superpowers/audits/2026-09-20-backend-cleanup-audit.md`（用户已批准批1-4 全做）
**Spec:** `docs/superpowers/specs/2026-09-20-backend-cleanup-audit-design.md`

## Global Constraints

- **冻结区不动代码**：kw 链路（service/kw/**、controller/Kw*.java、config/KwProperties.java、mapper/Kw*Mapper.java、sql/kw_init.sql）、登录鉴权链路、支付 v2 全套、3 个已知编译错误类
- **范围裁决（用户已定）**：删 CreativeToolService 孤儿服务；ProductServiceImpl 注释掉的 SKU 删除→只删注释不放开；CORS 暂不动；**LogUtil 密码脱敏跳过**（用户明确不需要）；@TableLogic（批4#2）与 fastjson 升级**本轮不做**（单独一期）
- 每批：修 → `mvn compile -pl spzx-manager -am`（需先 `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`）→ `mvn package -pl spzx-manager -am -DskipTests -q` → 重启 8501 冒烟（`lsof -ti:8501 | xargs kill; nohup java -jar spzx-manager/target/spzx-manager.jar > /tmp/spzx-manager.log 2>&1 &`，等 Started 日志 + `curl -s http://127.0.0.1:8501/admin/kw/config` 返回 code 208 + `kw_provider` 仍 3 行）→ 按主题 commit（conventional，勿 push）
- 无测试套件，勿跑 mvn test；不 git add 无关脏文件（target/、.DS_Store 等）
- MetaObjectHandler（批4#1）必须先 grep 现有手工 set 的取值来源并完全复刻语义，再删手工填充
- 每批实现者写报告到 `.superpowers/sdd/2026-09-20-backend-cleanup-fix/task-N-report.md`

## Task 1 = 批1 死代码删除（审查报告"批1"清单 13 项 + 补充）

补充项：ProductServiceImpl.java:111-114 删注释代码（不放开）；ProductServiceImpl Snowflake 提为静态常量（行为不变）。
CreativeToolService 接口+Impl 整对删除（拍板 A=删除，连带消掉批3#6 部分/批3#7 部分/批4#19）。
注意：MallRefundRecordDetail 实体/Mapper 被别处使用须保留，只删 service 接口+Impl；ProductSku 实体保留只删 mapper+XML。
Commit: `chore(cleanup): 删除全仓死代码（13处零引用复核）`

## Task 2 = 批3 日志与安全卫生（8 项，LogUtil 脱敏已裁决跳过）

清单=审查报告"批3"#3-#9（#1 跳过；#6/#7 中 CreativeTool 部分已随 Task 1 消失，只修 TaskProgress:311/:329 与 MallFarmOrder:291）。
Commit: `chore(cleanup): 日志与安全卫生（printStackTrace/System.out/吞异常/丢栈/openid打码/stdout外泄）`

## Task 3 = 批2 正确性与资源（11 项 bug 修复）

清单=审查报告"批2"#1-#11。ShellUtil 大一统（#5）：common-util 新建 ShellUtil.run(cmd, timeoutMs)——waitFor(timeout) 超时 destroyForcibly → 消费输出 → finally destroy + 流关闭；替换 TaskProgress 7 处 + Fanqie 3 处 + VisualScore runScript。
Commit 建议 3 个：`fix(cleanup): 菜单/报表/佣金/商品事务与NPE`、`fix(cleanup): 统一ShellUtil修复进程泄漏与挂死`、`fix(cleanup): 吞异常补日志与资源关闭`

## Task 4 = 批4a 常量/枚举/工具收敛（报告"批4"#3-#10，轻量）

CsvExportUtil、PlatformTypeEnum、OrderStatus/CardType 常量、httpGet 工具、@Value 外部化（Fanqie/Dashboard 路径+CDP 端口）、isFailedStatus 谓词、limit 1 统一、status 常量。
Commit: `refactor(cleanup): 常量枚举与工具收敛`

## Task 5 = 批4b 结构性收敛（报告"批4"#1、#11-#18，重量）

MetaObjectHandler（先复刻现有手工填充语义）、分页四行样板基类收敛、11 控制器 CRUD 泛型基类、PageParam 统一（新接口）、Excel BO 合并、SkuBind 自定义 mapper 分页、OrderBind/SyncAlert/Novel 查询下沉 Service、SourceFactory buildWrapper、MallRefundReport buildCard。
Commit: `refactor(cleanup): 分层与重复收敛（行为不变）`

## 最终验证（控制器执行）

- 全量 compile + package + 重启冒烟（kw 探针 + 登录页 200）
- 最终全分支 review（BASE=5461046 之后首 commit 起）
- 汇总报告给用户（修了什么/跳过什么/建议后续：@TableLogic、fastjson、登录链路 2 隐患）
