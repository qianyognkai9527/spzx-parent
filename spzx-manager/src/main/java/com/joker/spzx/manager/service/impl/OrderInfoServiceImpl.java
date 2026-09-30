package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.util.PageQueryUtil;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.OrderInfoMapper;
import com.joker.spzx.manager.mapper.OrderStatisticsMapper;
import com.joker.spzx.manager.service.OrderInfoService;
import com.joker.spzx.model.dto.order.OrderStatisticsDto;
import com.joker.spzx.model.entity.order.OrderInfo;
import com.joker.spzx.model.entity.order.OrderStatistics;
import com.joker.spzx.model.vo.order.OrderStatisticsVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.stream.Collectors;

/**
 * <p>
 * 订单 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class OrderInfoServiceImpl extends ServiceImpl<OrderInfoMapper, OrderInfo> implements OrderInfoService {

    @Autowired
    private OrderStatisticsMapper orderStatisticsMapper;

    @Override
    public OrderStatisticsVo getOrderStatisticsData(OrderStatisticsDto orderStatisticsDto) {

        // 查询统计结果数据
        List<OrderStatistics> orderStatisticsList = orderStatisticsMapper.selectSaticsList(orderStatisticsDto);

        //日期列表
        DateTimeFormatter df = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        List<String> dateList = orderStatisticsList.stream().map(orderStatistics -> orderStatistics.getOrderDate().format(df)).collect(Collectors.toList());

        //统计金额列表
        List<BigDecimal> amountList = orderStatisticsList.stream().map(OrderStatistics::getTotalAmount).collect(Collectors.toList());

        // 创建OrderStatisticsVo对象封装响应结果数据
        OrderStatisticsVo orderStatisticsVo = new OrderStatisticsVo();
        orderStatisticsVo.setDateList(dateList);
        orderStatisticsVo.setAmountList(amountList);

        // 返回数据
        return orderStatisticsVo;
    }

    @Override
    public IPage<OrderInfo> findByPage(Integer pageNum, Integer pageSize, Integer platformType, Long shopId, Integer orderStatus, String orderNo) {
        LambdaQueryWrapper<OrderInfo> wrapper = new LambdaQueryWrapper<OrderInfo>()
                .eq(platformType != null, OrderInfo::getPlatformType, platformType)
                .eq(shopId != null, OrderInfo::getShopId, shopId)
                .eq(orderStatus != null, OrderInfo::getOrderStatus, orderStatus)
                .like(StringUtils.hasText(orderNo), OrderInfo::getOrderNo, orderNo)
                .orderByDesc(OrderInfo::getCreateTime);
        return PageQueryUtil.page(this, pageNum, pageSize, wrapper);
    }
}
