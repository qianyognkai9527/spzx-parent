# 用 JRE 21 运行时（不需要 JDK，镜像更小）
# 你的项目要求 Java 21，eclipse-temurin 是常用的 OpenJDK 镜像
FROM eclipse-temurin:21-jre-alpine

# 设置时区，避免日志时间和本地差 8 小时
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

WORKDIR /app

# 把本地已构建好的 fat jar 拷进镜像，保留原始 jar 名便于排查
# （这个 jar 是 spring-boot-maven-plugin repackage 后的可执行 jar）
COPY spzx-manager/target/spzx-manager.jar spzx-manager.jar

# 端口通过环境变量 SERVER_PORT 覆盖，默认 8501
EXPOSE 8501

# 启动命令：用 shell 形式读取 JAVA_OPTS 环境变量
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar spzx-manager.jar"]
