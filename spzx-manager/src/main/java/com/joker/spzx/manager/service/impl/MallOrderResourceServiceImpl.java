package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallOrderResourceMapper;
import com.joker.spzx.manager.service.MallOrderResourceService;
import com.joker.spzx.model.entity.oper.MallOrderResource;
import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.compress.utils.Lists;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * <p>
 * 订单与图片视频关联关系表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-11 13:02:11
 */
@Service
public class MallOrderResourceServiceImpl extends ServiceImpl<MallOrderResourceMapper, MallOrderResource> implements MallOrderResourceService {

    @Override
    public List<Long> getSelectResources(Long orderId) {
        LambdaQueryWrapper<MallOrderResource> eq = lambdaQuery().getWrapper().eq(MallOrderResource::getOrderId, orderId);
        List<MallOrderResource> list = list(eq);
        if (CollectionUtils.isEmpty(list)) {
            return Lists.newArrayList();
        }
        return list.stream().map(MallOrderResource::getFileId).collect(Collectors.toList());

    }
}
