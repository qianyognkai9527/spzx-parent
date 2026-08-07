package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.ClickHouseStatisticsService;
import com.joker.spzx.model.dto.order.OrderStatisticsDto;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.order.OrderStatisticsVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
@RequestMapping("/admin/clickhouse")
public class ClickHouseStatisticsController {

    @Autowired
    private ClickHouseStatisticsService clickHouseStatisticsService;

    @GetMapping("/orderStatistics")
    public Result<OrderStatisticsVo> getOrderStatistics(OrderStatisticsDto dto) {
        OrderStatisticsVo vo = clickHouseStatisticsService.getOrderStatistics(dto);
        return Result.build(vo, ResultCodeEnum.SUCCESS);
    }
}