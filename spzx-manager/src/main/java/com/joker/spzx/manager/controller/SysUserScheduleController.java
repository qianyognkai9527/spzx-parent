package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.SysUserScheduleService;
import com.joker.spzx.model.dto.system.UserScheduleDtp;
import com.joker.spzx.model.entity.user.SysUserSchedule;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 每天日程安排表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-05-20 11:34:20
 */
@RestController
@RequestMapping("/admin/sys/userSchedule")
public class SysUserScheduleController {

    @Autowired
    private SysUserScheduleService sysUserScheduleService;

    @GetMapping("/list")
    public Result<IPage<SysUserSchedule>> pageList(UserScheduleDtp userScheduleDtp) {
        IPage<SysUserSchedule> page = sysUserScheduleService.pageList(userScheduleDtp);
        return Result.build(page);
    }

    @PostMapping("/save")
    public Result<String> save(@RequestBody SysUserSchedule sysUserSchedule) {
        sysUserScheduleService.saveData(sysUserSchedule);
        return Result.build(null);
    }

    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@PathVariable Long id) {
        sysUserScheduleService.removeById(id);
        return Result.build(null);
    }

}
