package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.OrderBindMapper;
import com.joker.spzx.manager.service.OrderBindService;
import com.joker.spzx.model.entity.order.OrderBind;
import org.springframework.stereotype.Service;

@Service
public class OrderBindServiceImpl extends ServiceImpl<OrderBindMapper, OrderBind> implements OrderBindService {
}
