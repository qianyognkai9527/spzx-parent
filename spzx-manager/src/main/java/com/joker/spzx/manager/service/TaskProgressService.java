package com.joker.spzx.manager.service;

import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;

/**
 * 任务进度看板服务
 */
public interface TaskProgressService {

    TaskOverviewVo getOverview();

    /**
     * 清理指定 CDP 端口的 Chrome 非关键标签页
     *
     * @param port CDP 端口 (9222/9223)
     * @return 关闭的标签页数量
     */
    int closeTabs(int port);
}
