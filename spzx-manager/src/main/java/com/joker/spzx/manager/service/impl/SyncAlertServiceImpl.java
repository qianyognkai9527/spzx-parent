package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SyncAlertMapper;
import com.joker.spzx.manager.service.SyncAlertService;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import org.springframework.stereotype.Service;

@Service
public class SyncAlertServiceImpl extends ServiceImpl<SyncAlertMapper, SyncAlert> implements SyncAlertService {
}
