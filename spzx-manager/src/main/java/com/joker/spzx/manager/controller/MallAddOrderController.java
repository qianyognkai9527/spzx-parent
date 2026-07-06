package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallAddOrderService;
import com.joker.spzx.model.dto.mall.MallAddOrderPageDto;
import com.joker.spzx.model.dto.mall.MallAddOrderPageVo;
import com.joker.spzx.model.entity.oper.MallAddOrder;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.BrushPersonStatVo;
import com.joker.spzx.model.vo.mall.BrushOrderStatVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 补单表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-06-10 14:05:10
 */
@RestController
@Tag(name = "补单表接口", description = "补单表接口")
@RequestMapping("/admin/mall/addOrder")
public class MallAddOrderController {

    @Autowired
    private MallAddOrderService addOrderService;


    @Operation(summary = "分页查询")
    @GetMapping("/findByPage")
    public Result<IPage<MallAddOrderPageVo>> findByPage(MallAddOrderPageDto mallAddOrderPageDto) {
        IPage<MallAddOrderPageVo> byPage = addOrderService.findByPage(mallAddOrderPageDto);
        return Result.build(byPage);
    }

    @Operation(summary = "新增补单")
    @PostMapping("/insert")
    public Result<String> insert(@RequestBody MallAddOrder mallAddOrder) {
        addOrderService.insertData(mallAddOrder);
        return Result.build(null);
    }

    @Operation(summary = "修改补单")
    @PostMapping("/update")
    public Result<String> update(@RequestBody MallAddOrder mallAddOrder) {
        addOrderService.updateData(mallAddOrder);
        return Result.build(null);
    }

    @Operation(summary = "删除补单")
    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@PathVariable Long id) {
        addOrderService.deleteById(id);
        return Result.build(null);
    }

    @Operation(summary = "批量返佣")
    @PostMapping("/settleCommission")
    public Result<String> settleCommission(@RequestBody List<Long> idList) {
        addOrderService.settleCommission(idList);
        return Result.build(null);
    }

    @Operation(summary = "刷单人员统计")
    @GetMapping("/brushPersonStat")
    public Result<List<BrushPersonStatVo>> brushPersonStat(@RequestParam(required = false) Integer platformType) {
        List<BrushPersonStatVo> stat = addOrderService.getBrushPersonStat(platformType);
        return Result.build(stat);
    }

    @Operation(summary = "补单统计报表")
    @GetMapping("/brushOrderStat")
    public Result<List<BrushOrderStatVo>> brushOrderStat(@RequestParam(required = false) Integer platformType,
                                                         @RequestParam(defaultValue = "month") String dimension) {
        List<BrushOrderStatVo> stat = addOrderService.getBrushOrderStat(platformType, dimension);
        return Result.build(stat);
    }
}
