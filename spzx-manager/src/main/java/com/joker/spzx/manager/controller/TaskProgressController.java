package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.TaskProgressService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 任务进度看板控制器
 */
@RestController
@RequestMapping(value = "/admin/taskProgress")
public class TaskProgressController {

    @Autowired
    private TaskProgressService taskProgressService;

    @GetMapping("/overview")
    public Result<TaskOverviewVo> getOverview() {
        return Result.build(taskProgressService.getOverview(), ResultCodeEnum.SUCCESS);
    }
}
