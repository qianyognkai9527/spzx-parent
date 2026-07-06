package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallProductService;
import com.joker.spzx.model.entity.oper.MallProduct;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品基本表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@RestController
@Tag(name = "我的商品", description = "我的商品")
@RequestMapping("/admin/mall/product")
public class MallProductController {

    @Autowired
    private MallProductService mallProductService;

    @Operation(summary = "分页查询")
    @GetMapping("/pageList/{pageNum}/{pageSize}")
    public Result<IPage<MallProduct>> page(@PathVariable Integer pageNum, @PathVariable Integer pageSize,
                                           @RequestParam Integer platformType,
                                           @RequestParam(required = false) String keyword,
                                           @RequestParam(required = false) String createTimeBegin,
                                           @RequestParam(required = false) String createTimeEnd) {
        IPage<MallProduct> page = mallProductService.pageList(pageNum, pageSize, platformType, keyword, createTimeBegin, createTimeEnd);
        return Result.build(page);
    }

    @PostMapping("/saveData")
    @Operation(summary = "新增")
    public Result<String> save(@RequestBody MallProduct mallProduct) {
        mallProductService.saveData(mallProduct);
        return Result.build(null);
    }


    @PutMapping("/update")
    @Operation(summary = "修改")
    public Result<String> update(@RequestBody MallProduct mallProduct) {
        mallProductService.updateData(mallProduct);
        return Result.build(null);
    }

    @Operation(summary = "查询所有")
    @GetMapping("/all")
    public Result<List<MallProduct>> list() {
        List<MallProduct> page = mallProductService.list();
        return Result.build(page);
    }

    @Operation(summary = "按平台类型查询所有商品")
    @GetMapping("/allByPlatformType")
    public Result<List<MallProduct>> listByPlatformType(@RequestParam Integer platformType) {
        List<MallProduct> list = mallProductService.list(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<MallProduct>()
                        .eq(MallProduct::getPlatformType, platformType)
                        .orderByDesc(MallProduct::getCreateTime)
        );
        return Result.build(list);
    }


}
