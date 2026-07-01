package com.joker.spzx.manager.task;

import cn.hutool.core.date.DateUtil;
import com.joker.spzx.manager.mapper.OrderInfoMapper;
import com.joker.spzx.manager.mapper.OrderStatisticsMapper;
import com.joker.spzx.model.entity.order.OrderStatistics;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Date;

@Component
@Slf4j
public class OrderStatisticsTask {

    @Autowired
    private OrderInfoMapper orderInfoMapper;

    @Autowired
    private OrderStatisticsMapper orderStatisticsMapper;

    @Scheduled(cron = "0 0 3 * * ?")
    public void orderTotalAmountStatistics() {
        String createTime = DateUtil.formatDate(DateUtil.offsetDay(new Date(), -1));
        OrderStatistics orderStatistics = orderInfoMapper.selectOrderStatistics(createTime);
        if (orderStatistics != null) {
            orderStatisticsMapper.insert(orderStatistics);
        }
    }

}