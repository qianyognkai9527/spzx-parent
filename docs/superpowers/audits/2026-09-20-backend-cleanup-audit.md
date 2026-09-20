# 后端全仓质量大扫除 · 审查报告

日期：2026-09-20 ｜ 方式：4 条只读主题线并行审查（死代码/重复魔法数/异常事务/日志安全），发现项已跨线去重
范围：spzx-model + spzx-common×3 + spzx-manager（~382 Java + 46 mapper XML + yml）
冻结区：kw 链路 / 登录鉴权 / 支付 v2 / 3 个已知编译错误类 —— 只记录未动
规格：`docs/superpowers/specs/2026-09-20-backend-cleanup-audit-design.md`

## 总览

| 批次 | 主题 | 项数 | 预估 | 风险 |
|---|---|---|---|---|
| 批1 | 死代码删除 | 13 | ~95min | 低（全部零引用复核） |
| 批2 | 正确性与资源（bug 修复） | 11 | ~155min | 中（改行为=修 bug，需冒烟） |
| 批3 | 日志与安全卫生 | 9 | ~75min | 低-中 |
| 批4 | 重复收敛/公共层（重构型） | 15 | ~300min | 中（建议今晚后再做） |
| 拍板项 | 需你决策的 6 项 | 6 | — | — |

---

## 批1 · 死代码删除（低风险，删前全部经全仓 grep 零引用复核）

1. `service/impl/MallFarmOrderServiceImpl.java:249-336` ｜ Critical ｜ ~87 行死代码簇（createEvaluationArchive 仅被注释调用，6 个私有 helper 仅被它引用；**删除同时消掉 ③线报的 Files.walk 流泄漏 2 处**）｜ 删两段 ｜ 20
2. `service/CreativeToolService.java` + `impl/CreativeToolServiceImpl.java` ｜ ⚠️转拍板项 A ｜ 363 行孤儿服务零注入零调用（智谱标题生成）｜ 用户定夺删除或保留
3. `config/ClickHouseConfig.java` + `config/ElasticsearchConfig.java` ｜ Critical ｜ `app.enable-infra=false` 永不激活且 yml 无对应键，Bean 无消费者，开启也会 @Value 启动失败 ｜ 删两配置类 ｜ 15
4. `service/OperLogSearchService.java` ｜ Critical ｜ ES 日志搜索零调用（同上门控），是 RestHighLevelClient 唯一消费点（删除后 ③线 #14 ES 吞异常项自动消失）｜ 删 ｜ 10
5. `config/HttpClientConfig.java` ｜ Important ｜ RestTemplate Bean 全仓零注入 ｜ 删 ｜ 5
6. `mapper/ProductSkuMapper.java` + `resources/mapper/ProductSkuMapper.xml` ｜ Important ｜ mapper 接口无注入点、XML 仅 namespace 自引（ProductSku 实体本身在用，保留）｜ 同删 ｜ 10
7. `model/entity/inventory/PlatformSku.java` + `mapper/PlatformSkuMapper.java` ｜ Important ｜ 实体+mapper 整对零引用 ｜ 删 ｜ 5
8. `model/entity/inventory/SourceSku.java` + `mapper/SourceSkuMapper.java` ｜ Important ｜ 同上 ｜ 删 ｜ 5
9. `service/MallRefundRecordDetailService.java` + Impl ｜ Important ｜ 20 行空壳 MP service 对零注入（**注意实体/Mapper 被别处使用须保留**）｜ 只删接口+Impl ｜ 5
10. `common-util/.../excel/ExcelUtil.java:29,42,71` + `PreHeaderListener` + `CellPosition` ｜ Important ｜ Excel 死链 ~200 行（3 个零调用重载连带 2 个死类）｜ 删 ｜ 30
11. `model/dto/product/SkuSaleDto.java` ｜ Minor ｜ 零引用 DTO ｜ 删 ｜ 2
12. `model/dto/system/SysOperLogDto.java` ｜ Minor ｜ 零引用 DTO ｜ 删 ｜ 2
13. `model/vo/mall/RefundReportSimplePageVo.java` + `model/vo/product/CategoryExcelVo.java` ｜ Minor ｜ 零引用 VO×2 ｜ 删 ｜ 4

## 批2 · 正确性与资源（真 bug 修复，每项修完需重启冒烟）

1. `SysMenuServiceImpl.java:70` ｜ Critical ｜ `nonNull` 误写 `isNull` → 新增根菜单必 NPE，且 insert 已落库无法回滚 ｜ 改 nonNull + saveData 加 @Transactional ｜ 20
2. `MallRefundRecordServiceImpl.java:160` ｜ Critical ｜ generate() 3 次写无事务；169 判空分支逻辑反了 → null 引用必 NPE，报表卡"生成中" ｜ @Transactional + 判空改抛异常 ｜ 40
3. `MallAddOrderServiceImpl.java:62` ｜ Critical ｜ settleCommission 循环 getById+updateById（N+1）且批量结算无事务，中途失败部分结算 ｜ listByIds 预取 + @Transactional ｜ 20
4. `ProductServiceImpl.java:77` ｜ Critical ｜ updateDataById 商品更新+工厂计数 3 写无事务，失败计数漂移 ｜ 加 @Transactional ｜ 10
5. `VisualScoreServiceImpl.java:162` + `TaskProgressServiceImpl` 7 处 + `FanqiePublishServiceImpl` 3 处 ｜ Critical ｜ ProcessBuilder stdout 读到 EOF 才 waitFor（脚本挂起=HTTP 线程永久挂死）、流从不 close、进程从不 destroy（每次刷新泄漏 fd）｜ 抽 common-util `ShellUtil.run()`（waitFor(timeout)→消费输出→finally destroy），10+ 处统一替换 ｜ 60
6. `TaskProgressServiceImpl.java:182/271/284` ｜ Important ｜ HttpURLConnection 流异常路径不关闭 ｜ try-with-resources ｜ 10
7. `TaskProgressServiceImpl.java:628-653` ｜ Important ｜ readJsonFile/countJsonlLines/readLogTail 静默吞异常 → 看板把"读取失败"渲染成"无数据" ｜ catch 里 log.warn ｜ 10
8. `FanqiePublishServiceImpl.java:102` ｜ Important ｜ checkRunning 异常静默返回 null → start() 误判未运行重复拉起发布脚本 ｜ log.error + 返回失败 ｜ 10
9. `DashboardServiceImpl.java:107` ｜ Important ｜ getTaskAnomalies catch 完全静默（连 log 都没有）｜ 补 log.warn ｜ 5
10. `MallFarmOrderServiceImpl.java:366` ｜ Important ｜ downloadMediaFiles 循环内吞下载失败，zip 照常交付缺文件无标记 ｜ 收集失败清单回传 ｜ 15
11. `MallFarmOrderServiceImpl.java:215/377` ｜ Minor ｜ zos.close/finish 顺序颠倒重复关闭；zip 响应头已写后再改写 JSON 错误体 ｜ 修正流处理 ｜ 15

## 批3 · 日志与安全卫生

1. `common-log/.../LogUtil.java:56` ｜ Critical ｜ @Log 切面把 POST/PUT 全量入参存 sys_oper_log，**SysUser 密码明文落审计表** ｜ 序列化前按字段名脱敏（password/token 等）｜ 30
2. `spzx-model/src/test/GeneratorCode.java:20` ｜ Critical ｜ **硬编码 MySQL root 密码提交进仓库**（非本机库密码）｜ 改环境变量读取 ｜ 10
3. `config/LoginAuthInterceptor.java:72` ｜ Important ｜ e.printStackTrace() 直打 stderr ｜ 改 log.error ｜ 3
4. `MallRefundRecordServiceImpl.java:208-309`（10 处）+ `MallRefundReportController.java:56` ｜ Important ｜ System.out 调试残留（含逐单 orderId）｜ 删或改 log.debug ｜ 15
5. `common-util/.../DefaultExcelListener.java:60-70` ｜ Important ｜ `if(isDebugEnabled())` 包 log.error → 错误永远不落日志 ｜ 去掉条件 ｜ 5
6. `CreativeToolServiceImpl.java:202/314` + `TaskProgressServiceImpl.java:311` ｜ Important ｜ 空 catch 完全静默 ｜ 补 log.warn（若拍板项 A 选删除则自动消失）｜ 10
7. `CreativeToolServiceImpl.java:84`、`TaskProgressServiceImpl.java:329`、`MallFarmOrderServiceImpl.java:291` ｜ Important ｜ log.error 只记 e.getMessage() 丢堆栈 ｜ 传异常对象 ｜ 10
8. `WxLoginServiceImpl.java:192` ｜ Minor ｜ openid 明文入日志（准 PII）｜ 打码 ｜ 5
9. `VisualScoreServiceImpl.java:176-182` ｜ Minor ｜ Python 脚本 stdout 全文塞进 ServiceException 返回前端（内部路径外泄）｜ 对外泛化、详情进日志 ｜ 10

## 批4 · 重复收敛/公共层（重构型，建议今晚后做）

1. 25 个 Impl 手工填 createBy/createTime 等审计字段（27 处）｜ 加 MyBatis-Plus MetaObjectHandler 统一填充 ｜ 60
2. 全仓 41 处 `.eq(isDeleted,0)` 手工过滤 + 6 处手工置 1，无 @TableLogic 且 isDeleted/delFlag 两套并存 ｜ BaseEntity @TableLogic 全局化 ｜ 60 ⚠️高影响需单独评审
3. ProductController/SourceFactoryController CSV 导出样板逐字重复 ｜ 抽 CsvExportUtil ｜ 30
4. platformType 1=淘宝/2=抖音 映射重复 3 处且 Dashboard 版已漂移 ｜ 建 PlatformTypeEnum ｜ 15
5. MallRefundRecordServiceImpl 订单状态/卡类型中文字面量 9+ 处 ｜ 常量类/枚举 ｜ 20
6. TaskProgressServiceImpl HttpURLConnection GET 样板 4 处超时不一 ｜ 抽 httpGet 工具 ｜ 20
7. FanqiePublish/Dashboard 硬编码 /Users/qyk9527 路径与 CDP 端口（TaskProgress 4 处）｜ @Value 外部化 ｜ 35
8. 失败状态判定 contains("fail"/"error"/"risk") 重复 3 处已漂移 ｜ 抽谓词 ｜ 10
9. `.last("limit 1")` 三种写法 14 处 ｜ 统一 ｜ 10
10. status 0/1 语义跨实体相反无常量 ｜ 各配常量 ｜ 15
11. Page+wrapper 分页四行样板 15+ 处 ｜ ServiceImpl 基类 pageQuery 收敛 ｜ 25
12. 11 个控制器 CRUD 四端点样板 ｜ 泛型基类（可选）｜ 30
13. 分页参数一半手写一半 PageParam DTO ｜ 新接口统一 PageParam ｜ 30
14. SecondOrderExcelBo/OrderSimpleExcelBo 仅差一列 ｜ 合并 ｜ 15
15. SkuBindServiceImpl 手拼 SQL+offset+Controller 冒充分页 ｜ 自定义 mapper 分页 ｜ 25
16. OrderBind/SyncAlert/Novel Controller 层直查库混业务 ｜ 下沉 Service ｜ 20
17. SourceFactory pageList/exportList 25 行重复 ｜ 抽 buildWrapper ｜ 15
18. MallRefundReport 6 个统计卡片拼装块 ｜ buildCard 工厂 ｜ 15
19. CreativeTool 第三份手写 chat-completions 实现 ｜ 抽通用 OpenAI 客户端（若孤儿服务删除则消失）｜ 40

## 拍板项（需你决策）

- **A. CreativeToolService 孤儿服务（363 行）**：删除（git 可找回）还是保留等接 Controller？（AGENTS/spec 曾记"等接 Controller 时再说"）——删除则批3#6、批4#19 自动消失
- **B. ProductServiceImpl.java:111-114**：注释掉的 SKU 逻辑删除疑似漏删——放开还是删注释？
- **C. CORS**（WebMvcConfiguration:29）：`allowedOriginPatterns("*")+allowCredentials(true)`——收紧成域名白名单还是本地单管理员暂不动？
- **D. fastjson 2.0.21 → 2.0.4x**：有 CVE 修复，但 JSON 行为可能微变，建议今晚后单独升
- **E. @TableLogic 全局逻辑删除（批4#2）**：收益大但动全仓删除语义，强烈建议单独一期
- **F. 逻辑删除批次顺序**：无

## 冻结区备忘录（只记录，本轮不动；今晚后建议单独安排）

1. ⚠️ `SysUser.password` 无 @JsonIgnore——login/getUserInfo 返回体把密码哈希带去前端（登录链路）
2. ⚠️ 登录密码哈希为**无盐 MD5**（SysUserServiceImpl:75,125）（登录链路，改动需迁移方案）
3. kw 链路未发现 apiKey 入日志；KwAiClient/KwProviderController 的 HTTP 调用均已带 timeout
4. Redis key 字面量 `user:login:` 在拦截器与 service 重复（WxLoginServiceImpl:45 已有常量未共享）
