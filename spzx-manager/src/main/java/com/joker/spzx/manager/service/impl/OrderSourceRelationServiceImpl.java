package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.mapper.OrderSourceRelationMapper;
import com.joker.spzx.manager.service.OrderSourceRelationService;
import com.joker.spzx.model.entity.order.OrderSourceRelation;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * <p>
 * 本地订单与货源订单关联 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-07-01 10:00:00
 */
@Service
public class OrderSourceRelationServiceImpl extends ServiceImpl<OrderSourceRelationMapper, OrderSourceRelation> implements OrderSourceRelationService {

    @Override
    public IPage<OrderSourceRelation> findByPage(Integer pageNum, Integer pageSize, OrderSourceRelation queryDto) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(OrderSourceRelation::getIsDeleted, 0)
                .eq(queryDto.getPlatformType() != null, OrderSourceRelation::getPlatformType, queryDto.getPlatformType())
                .eq(StringUtils.hasText(queryDto.getOrderNo()), OrderSourceRelation::getOrderNo, queryDto.getOrderNo())
                .eq(StringUtils.hasText(queryDto.getSourceOrderNo()), OrderSourceRelation::getSourceOrderNo, queryDto.getSourceOrderNo())
                .eq(queryDto.getPlatformProductId() != null, OrderSourceRelation::getPlatformProductId, queryDto.getPlatformProductId())
                .eq(queryDto.getSourceProductId() != null, OrderSourceRelation::getSourceProductId, queryDto.getSourceProductId())
                .eq(queryDto.getOrderStatus() != null, OrderSourceRelation::getOrderStatus, queryDto.getOrderStatus())
                .orderByDesc(OrderSourceRelation::getCreateTime);
        return page(new Page<>(pageNum, pageSize), wrapper);
    }

    @Override
    public OrderSourceRelation getById(Long id) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(OrderSourceRelation::getId, id)
                .eq(OrderSourceRelation::getIsDeleted, 0);
        return getOne(wrapper);
    }

    @Override
    public void saveData(OrderSourceRelation orderSourceRelation) {
        // 校验唯一性：同一平台下，本地订单号+货源订单号不能重复
        checkDuplicate(orderSourceRelation, null);
        orderSourceRelation.setIsDeleted(0);
        save(orderSourceRelation);
    }

    @Override
    public void updateData(OrderSourceRelation orderSourceRelation) {
        // 校验唯一性：排除自身后，同一平台下同订单号不能重复
        checkDuplicate(orderSourceRelation, orderSourceRelation.getId());
        updateById(orderSourceRelation);
    }

    @Override
    public void deleteById(Long id) {
        OrderSourceRelation orderSourceRelation = new OrderSourceRelation();
        orderSourceRelation.setId(id);
        orderSourceRelation.setIsDeleted(1);
        updateById(orderSourceRelation);
    }

    /**
     * 校验同一平台下，本地订单号 + 货源订单号是否已存在
     */
    private void checkDuplicate(OrderSourceRelation entity, Long excludeId) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(OrderSourceRelation::getIsDeleted, 0)
                .eq(OrderSourceRelation::getPlatformType, entity.getPlatformType())
                .eq(OrderSourceRelation::getOrderNo, entity.getOrderNo())
                .eq(OrderSourceRelation::getSourceOrderNo, entity.getSourceOrderNo())
                .ne(excludeId != null, OrderSourceRelation::getId, excludeId);
        long count = count(wrapper);
        if (count > 0) {
            throw new ServiceException(ResultCodeEnum.DATA_ERROR);
        }
    }

}
