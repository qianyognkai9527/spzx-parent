package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.order.OrderBind;

public interface OrderBindService extends IService<OrderBind> {

    IPage<OrderBind> findByPage(Integer pageNum, Integer pageSize, String localOrderNo, String sourceOrderNo, Integer bindStatus);
}
