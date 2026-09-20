package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.inventory.SyncAlert;

public interface SyncAlertService extends IService<SyncAlert> {

    IPage<SyncAlert> findByPage(Integer pageNum, Integer pageSize, Integer status);

    void markRead(Long id);

    void markAllRead();

    Long unreadCount();
}
