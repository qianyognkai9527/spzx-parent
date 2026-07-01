package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.order.OrderSourceRelation;
import org.apache.ibatis.annotations.Mapper;

/**
 * <p>
 * 本地订单与货源订单关联 Mapper 接口
 * </p>
 *
 * @author joker
 * @since 2025-07-01 10:00:00
 */
@Mapper
public interface OrderSourceRelationMapper extends BaseMapper<OrderSourceRelation> {

}
