package com.joker.spzx.common.util;

/**
 * 任务进度状态判定工具
 */
public final class TaskStatusUtil {

    private TaskStatusUtil() {
    }

    /**
     * 进度状态是否为失败（含 fail/error/risk 任一关键字）
     */
    public static boolean isFailedStatus(String status) {
        return status != null
                && (status.contains("fail") || status.contains("error") || status.contains("risk"));
    }
}
