package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.order.OrderInfo;
import com.joker.spzx.model.entity.order.OrderStatistics;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * <p>
 * 订单 Mapper 接口
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Mapper
public interface OrderInfoMapper extends BaseMapper<OrderInfo> {

    OrderStatistics selectOrderStatistics(@Param("createTime") String createTime, @Param("platformType") Integer platformType);
}
