package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.OrderInfoService;
import com.joker.spzx.model.dto.order.OrderStatisticsDto;
import com.joker.spzx.model.entity.order.OrderInfo;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.order.OrderStatisticsVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "订单管理")
@RestController
@RequestMapping(value = "/admin/order/orderInfo")
public class OrderInfoController {

    @Autowired
    private OrderInfoService orderInfoService;

    @Operation(summary = "订单统计")
    @GetMapping("/getOrderStatisticsData")
    public Result<OrderStatisticsVo> getOrderStatisticsData(OrderStatisticsDto orderStatisticsDto) {
        OrderStatisticsVo orderStatisticsVo = orderInfoService.getOrderStatisticsData(orderStatisticsDto);
        return Result.build(orderStatisticsVo, ResultCodeEnum.SUCCESS);
    }

    @Operation(summary = "订单分页列表(统一视图,含平台/店铺/状态/订单号筛选)")
    @GetMapping("/findByPage/{pageNum}/{pageSize}")
    public Result findByPage(@PathVariable Integer pageNum,
                             @PathVariable Integer pageSize,
                             @RequestParam(required = false) Integer platformType,
                             @RequestParam(required = false) Long shopId,
                             @RequestParam(required = false) Integer orderStatus,
                             @RequestParam(required = false) String orderNo) {
        return Result.build(orderInfoService.findByPage(pageNum, pageSize, platformType, shopId, orderStatus, orderNo));
    }

    @Operation(summary = "订单详情")
    @GetMapping("/getDetail/{id}")
    public Result<OrderInfo> getDetail(@PathVariable Long id) {
        return Result.build(orderInfoService.getById(id));
    }

}