package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SyncAlertMapper;
import com.joker.spzx.manager.service.SyncAlertService;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;

@Service
public class SyncAlertServiceImpl extends ServiceImpl<SyncAlertMapper, SyncAlert> implements SyncAlertService {

    @Override
    public IPage<SyncAlert> findByPage(Integer pageNum, Integer pageSize, Integer status) {
        LambdaQueryWrapper<SyncAlert> wrapper = new LambdaQueryWrapper<SyncAlert>()
                .eq(status != null, SyncAlert::getStatus, status)
                .orderByDesc(SyncAlert::getCreateTime);
        return PageQueryUtil.page(this, pageNum, pageSize, wrapper);
    }

    @Override
    public void markRead(Long id) {
        lambdaUpdate()
                .eq(SyncAlert::getId, id)
                .set(SyncAlert::getStatus, SyncAlert.STATUS_READ)
                .update();
    }

    @Override
    public void markAllRead() {
        lambdaUpdate()
                .eq(SyncAlert::getStatus, SyncAlert.STATUS_UNREAD)
                .set(SyncAlert::getStatus, SyncAlert.STATUS_READ)
                .update();
    }

    @Override
    public Long unreadCount() {
        return lambdaQuery()
                .eq(SyncAlert::getStatus, SyncAlert.STATUS_UNREAD)
                .count();
    }
}
