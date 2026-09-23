package com.joker.spzx.manager.task;

import cn.hutool.core.date.DateUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.model.enums.PlatformTypeEnum;
import com.joker.spzx.manager.mapper.OrderInfoMapper;
import com.joker.spzx.manager.mapper.OrderStatisticsMapper;
import com.joker.spzx.model.entity.order.OrderStatistics;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.Date;
import java.util.List;

@Component
@Slf4j
public class OrderStatisticsTask {

    @Autowired
    private OrderInfoMapper orderInfoMapper;

    @Autowired
    private OrderStatisticsMapper orderStatisticsMapper;

    /**
     * 每天凌晨 3 点统计各平台的订单数据（1-淘宝, 2-抖音）
     * 先删同日同平台旧行再插入，保证补跑/重跑幂等
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void orderTotalAmountStatistics() {
        String createTime = DateUtil.formatDate(DateUtil.offsetDay(new Date(), -1));
        LocalDate statDate = LocalDate.parse(createTime);
        List<Integer> platforms = List.of(
                PlatformTypeEnum.TAOBAO.getCode(),
                PlatformTypeEnum.DOUYIN.getCode());
        for (Integer platformType : platforms) {
            OrderStatistics orderStatistics = orderInfoMapper.selectOrderStatistics(createTime, platformType);
            if (orderStatistics != null) {
                orderStatistics.setPlatformType(platformType);
                orderStatisticsMapper.delete(new LambdaQueryWrapper<OrderStatistics>()
                        .eq(OrderStatistics::getOrderDate, statDate)
                        .eq(OrderStatistics::getPlatformType, platformType));
                orderStatisticsMapper.insert(orderStatistics);
            }
        }
    }

}