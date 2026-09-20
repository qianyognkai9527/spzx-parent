package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
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
        return Result.build(syncAlertService.findByPage(pageNum, pageSize, status));
    }

    @PutMapping("/read/{id}")
    public Result<String> read(@PathVariable Long id) {
        syncAlertService.markRead(id);
        return Result.build(null);
    }

    @PutMapping("/readAll")
    public Result<String> readAll() {
        syncAlertService.markAllRead();
        return Result.build(null);
    }

    @GetMapping("/count")
    public Result<Long> count() {
        return Result.build(syncAlertService.unreadCount());
    }
}
