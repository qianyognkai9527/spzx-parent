package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.TaskProgressService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;

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

    @PostMapping("/closeTabs")
    public Result<Map<String, Object>> closeTabs(@RequestParam Integer port) {
        int closed = taskProgressService.closeTabs(port);
        Map<String, Object> data = new HashMap<>();
        data.put("closed", closed);
        data.put("port", port);
        return Result.build(data, ResultCodeEnum.SUCCESS);
    }
}
