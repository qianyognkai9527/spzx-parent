package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.OrderBindMapper;
import com.joker.spzx.manager.service.OrderBindService;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.entity.order.OrderBind;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class OrderBindServiceImpl extends ServiceImpl<OrderBindMapper, OrderBind> implements OrderBindService {

    @Override
    public IPage<OrderBind> findByPage(Integer pageNum, Integer pageSize, String localOrderNo, String sourceOrderNo, Integer bindStatus) {
        LambdaQueryWrapper<OrderBind> wrapper = new LambdaQueryWrapper<OrderBind>()
                .like(StringUtils.hasText(localOrderNo), OrderBind::getLocalOrderNo, localOrderNo)
                .like(StringUtils.hasText(sourceOrderNo), OrderBind::getSourceOrderNo, sourceOrderNo)
                .eq(bindStatus != null, OrderBind::getBindStatus, bindStatus)
                .orderByDesc(OrderBind::getCreateTime);
        return PageQueryUtil.page(this, pageNum, pageSize, wrapper);
    }
}
