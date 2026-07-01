#!/bin/bash
# ============================================================
# 自动部署监听脚本
# 用法：在项目根目录执行 ./auto-deploy.sh
# 它会监听 spzx-manager/target/spzx-manager.jar
# 当 jar 修改时间变化时，自动执行：
#   1. docker build（构建新镜像）
#   2. kubectl rollout restart（k8s 滚动重启，拉新镜像）
# ============================================================

JAR="spzx-manager/target/spzx-manager.jar"
IMAGE="spzx-manager:latest"
DEPLOY="spzx-manager"
POLL_INTERVAL=3   # 每 3 秒检查一次

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== 自动部署监听已启动 ===${NC}"
echo -e "监听文件: ${YELLOW}${JAR}${NC}"
echo -e "镜像名:   ${YELLOW}${IMAGE}${NC}"
echo -e "部署名:   ${YELLOW}${DEPLOY}${NC}"
echo -e "检查间隔: ${YELLOW}${POLL_INTERVAL}秒${NC}"
echo -e "按 Ctrl+C 停止"
echo ""

if [ ! -f "$JAR" ]; then
    echo -e "${YELLOW}警告: jar 文件还不存在，先在 IDEA 里 build 一次${NC}"
fi

LAST_MTIME=0

while true; do
    if [ ! -f "$JAR" ]; then
        sleep "$POLL_INTERVAL"
        continue
    fi

    # 获取 jar 的修改时间（秒级时间戳）
    CURRENT_MTIME=$(stat -f %m "$JAR" 2>/dev/null || stat -c %Y "$JAR" 2>/dev/null)

    if [ "$CURRENT_MTIME" != "$LAST_MTIME" ] && [ "$LAST_MTIME" != "0" ]; then
        echo ""
        echo -e "${GREEN}[$(date '+%H:%M:%S')] 检测到 jar 更新，开始重新部署...${NC}"

        # 第1步：构建镜像
        echo -e "${CYAN}[1/2] docker build...${NC}"
        if docker build -t "$IMAGE" . > /tmp/docker-build.log 2>&1; then
            echo -e "${GREEN}    镜像构建成功${NC}"
        else
            echo -e "\033[0;31m    镜像构建失败，查看 /tmp/docker-build.log${NC}"
            tail -10 /tmp/docker-build.log
            LAST_MTIME="$CURRENT_MTIME"
            sleep "$POLL_INTERVAL"
            continue
        fi

        # 第2步：滚动重启
        echo -e "${CYAN}[2/2] kubectl rollout restart...${NC}"
        if kubectl rollout restart deployment/"$DEPLOY" > /dev/null 2>&1; then
            echo -e "${GREEN}    滚动重启已触发${NC}"
        else
            echo -e "\033[0;31m    滚动重启失败${NC}"
        fi

        echo -e "${GREEN}[$(date '+%H:%M:%S')] 完成，k8s 正在拉起新 Pod...${NC}"
        echo -e "${YELLOW}    用 kubectl logs -f -l app=${DEPLOY} 看启动日志${NC}"
    fi

    LAST_MTIME="$CURRENT_MTIME"
    sleep "$POLL_INTERVAL"
done
