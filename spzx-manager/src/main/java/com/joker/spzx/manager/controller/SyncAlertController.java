package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.SyncAlertService;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 库存同步提醒控制器
 */
@RestController
@RequestMapping("/admin/syncAlert")
public class SyncAlertController {

    @Autowired
    private SyncAlertService syncAlertService;

    @GetMapping("/list")
    public Result<IPage<SyncAlert>> list(@RequestParam(defaultValue = "1") Integer pageNum,
                                         @RequestParam(defaultValue = "10") Integer pageSize,
                                         @RequestParam(required = false) Integer status) {
        Page<SyncAlert> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<SyncAlert> wrapper = new LambdaQueryWrapper<SyncAlert>()
                .eq(status != null, SyncAlert::getStatus, status)
                .orderByDesc(SyncAlert::getCreateTime);
        return Result.build(syncAlertService.page(page, wrapper));
    }

    @PutMapping("/read/{id}")
    public Result<String> read(@PathVariable Long id) {
        syncAlertService.lambdaUpdate()
                .eq(SyncAlert::getId, id)
                .set(SyncAlert::getStatus, 1)
                .update();
        return Result.build(null);
    }

    @PutMapping("/readAll")
    public Result<String> readAll() {
        syncAlertService.lambdaUpdate()
                .eq(SyncAlert::getStatus, 0)
                .set(SyncAlert::getStatus, 1)
                .update();
        return Result.build(null);
    }

    @GetMapping("/count")
    public Result<Long> count() {
        return Result.build(syncAlertService.lambdaQuery()
                .eq(SyncAlert::getStatus, 0)
                .count());
    }
}
