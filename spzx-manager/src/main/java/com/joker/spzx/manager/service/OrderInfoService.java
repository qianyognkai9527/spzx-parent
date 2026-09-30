package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.order.OrderStatisticsDto;
import com.joker.spzx.model.entity.order.OrderInfo;
import com.joker.spzx.model.vo.order.OrderStatisticsVo;

/**
 * <p>
 * 订单 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
public interface OrderInfoService extends IService<OrderInfo> {

    OrderStatisticsVo getOrderStatisticsData(OrderStatisticsDto orderStatisticsDto);

    IPage<OrderInfo> findByPage(Integer pageNum, Integer pageSize, Integer platformType, Long shopId, Integer orderStatus, String orderNo);
}
