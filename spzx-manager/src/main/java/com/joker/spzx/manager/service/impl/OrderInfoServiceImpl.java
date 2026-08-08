package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
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
        List<String> dateList = orderStatisticsList.stream().map(orderStatistics -> orderStatistics.getCreateTime().format(df)).collect(Collectors.toList());

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
    public IPage<OrderInfo> findByPage(Integer pageNum, Integer pageSize, Integer platformType, Integer orderStatus, String orderNo) {
        Page<OrderInfo> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<OrderInfo> wrapper = new LambdaQueryWrapper<OrderInfo>()
                .eq(platformType != null, OrderInfo::getPlatformType, platformType)
                .eq(orderStatus != null, OrderInfo::getOrderStatus, orderStatus)
                .like(StringUtils.hasText(orderNo), OrderInfo::getOrderNo, orderNo)
                .eq(OrderInfo::getIsDeleted, 0)
                .orderByDesc(OrderInfo::getCreateTime);
        return this.page(page, wrapper);
    }
}
