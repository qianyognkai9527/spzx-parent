package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.OrderSourceRelationService;
import com.joker.spzx.model.entity.order.OrderSourceRelation;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 本地订单与货源订单关联 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-07-01 10:00:00
 */
@Tag(name = "订单货源关联", description = "本地订单与货源订单关联管理")
@RestController
@RequestMapping(value = "/admin/order/orderSourceRelation")
public class OrderSourceRelationController {

    private final OrderSourceRelationService orderSourceRelationService;

    public OrderSourceRelationController(OrderSourceRelationService orderSourceRelationService) {
        this.orderSourceRelationService = orderSourceRelationService;
    }

    @PostMapping("/findByPage/{pageNum}/{pageSize}")
    @Operation(summary = "分页查询订单关联关系")
    public Result<IPage<OrderSourceRelation>> findByPage(@PathVariable Integer pageNum,
                                                         @PathVariable Integer pageSize,
                                                         @RequestBody OrderSourceRelation queryDto) {
        IPage<OrderSourceRelation> page = orderSourceRelationService.findByPage(pageNum, pageSize, queryDto);
        return Result.build(page, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/getById/{id}")
    @Operation(summary = "根据ID查询订单关联关系")
    public Result<OrderSourceRelation> getById(@PathVariable Long id) {
        OrderSourceRelation entity = orderSourceRelationService.getById(id);
        return Result.build(entity, ResultCodeEnum.SUCCESS);
    }

    @PostMapping("/save")
    @Operation(summary = "新增订单关联关系")
    public Result<Void> save(@RequestBody OrderSourceRelation orderSourceRelation) {
        orderSourceRelationService.saveData(orderSourceRelation);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @PutMapping("/updateById")
    @Operation(summary = "修改订单关联关系")
    public Result<Void> updateById(@RequestBody OrderSourceRelation orderSourceRelation) {
        orderSourceRelationService.updateData(orderSourceRelation);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @DeleteMapping("/deleteById/{id}")
    @Operation(summary = "删除订单关联关系")
    public Result<Void> deleteById(@PathVariable Long id) {
        orderSourceRelationService.deleteById(id);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

}
