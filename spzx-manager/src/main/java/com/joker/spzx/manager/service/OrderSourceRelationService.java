package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.order.OrderSourceRelation;

/**
 * <p>
 * 本地订单与货源订单关联 服务类
 * </p>
 *
 * @author joker
 * @since 2025-07-01 10:00:00
 */
public interface OrderSourceRelationService extends IService<OrderSourceRelation> {

    IPage<OrderSourceRelation> findByPage(Integer pageNum, Integer pageSize, OrderSourceRelation queryDto);

    OrderSourceRelation getById(Long id);

    void saveData(OrderSourceRelation orderSourceRelation);

    void updateData(OrderSourceRelation orderSourceRelation);

    void deleteById(Long id);

}
