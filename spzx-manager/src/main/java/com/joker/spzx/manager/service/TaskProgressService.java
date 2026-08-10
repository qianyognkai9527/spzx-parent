package com.joker.spzx.manager.service;

import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;

/**
 * 任务进度看板服务
 */
public interface TaskProgressService {

    TaskOverviewVo getOverview();
}
