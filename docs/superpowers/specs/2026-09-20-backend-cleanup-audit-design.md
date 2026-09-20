# 后端全仓质量大扫除 · 设计文档

日期：2026-09-20 ｜ 状态：已用户批准（对话确认"OK的"）
背景：用户要求"后端全局代码优化"，经澄清确认为**全仓库质量大扫除**（非性能/结构重构），打法为**先只读审查、后按用户挑选分批修**。今晚用户将实际运行 AI选词 任务，故冻结其依赖链路。

## 1. 目标与原则

- **零行为变更**：只清理死代码/重复/规范偏离，不改任何运行时行为
- 两阶段：A 只读审查产出分级清单 → 用户挑选 → B 分批修复（每批编译+冒烟+独立 commit）
- 无测试套件（禁止 mvn test），验证手段 = `mvn compile` + 重启冒烟

## 2. 冻结区（审查可记录 Critical 一句话，不出修复项、本轮绝不动代码）

1. **kw 全链路**：`service/kw/**`、`controller/Kw*.java`、`config/KwProperties.java`、`mapper/Kw*Mapper.java`、`sql/kw_init.sql`
2. **登录鉴权链路**：LoginInterceptor/AuthContextUtil 等登录拦截所依赖的类
3. **支付 v2 在建代码**：`PaymentFacade`、`pay/strategy/**`、`pay/handler/**`、状态机、MQ 事件、`IdempotentService`、`DistributedLockService`、`PayV2Controller`、`NotifyController`
4. 3 个已知预存编译错误类：`AbstractWechatPayStrategy` / `PaypalOrderStrategy` / `StripeCardStrategy`

## 3. 阶段 A：只读审查（4 条并行主题线）

| 线 | 主题 | 要点 |
|---|---|---|
| ① | 死代码 | 未引用类/方法/Bean、注释掉的代码块、遗留 excel/api 类、无用配置。**判定规则：候选必须全仓 grep 引用（含 mapper XML、反射、Spring Bean 名）确认为零才可入清单，防误报** |
| ② | 重复与魔法数 | 跨 Controller/Service 复制粘贴、硬编码 URL/路径/数字、重复工具方法 |
| ③ | 异常与事务 | 吞异常、缺 @Transactional 的多写操作、MyBatis-Plus 循环查库（N+1）、资源泄漏 |
| ④ | 日志与安全 | System.out/printStackTrace、日志敏感信息、log4j2 规范偏离 |

产出：每线 ≤25 条，每条 `path:line ｜ 级别(Critical/Important/Minor) ｜ 问题 ｜ 建议修法 ｜ 预估分钟`；汇总进审查报告 `docs/superpowers/audits/2026-09-20-backend-cleanup-audit.md`。

## 4. 阶段 B：分批修复（用户挑选后启动，另出实施计划）

- 按主题分批：修 → `mvn compile` → 重启 8501 冒烟（启动日志 + `/admin/kw/config` 208 探针）→ 每主题一个 conventional commit
- 批间可回滚；kw 相关发现项只入清单，今晚之后处理
- 验证红线：每批必须编译零新增错误 + 冒烟通过才算完成

## 5. 明确不做

性能调优、分层/模块边界重构、支付枚举/策略层改造、行为变更、前端（另行安排）。
