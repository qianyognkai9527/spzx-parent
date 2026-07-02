package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.ProductSpecService;
import com.joker.spzx.model.entity.product.ProductSpec;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品规格 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@RestController
@RequestMapping(value = "/admin/product/productSpec")
public class ProductSpecController {

    @Autowired
    private ProductSpecService productSpecService;

    @GetMapping("/{page}/{limit}")
    public Result<IPage<ProductSpec>> findByPage(@PathVariable Integer page, @PathVariable Integer limit,
                                                  @RequestParam Integer platformType) {
        IPage<ProductSpec> pageInfo = productSpecService.findByPage(page, limit, platformType);
        return Result.build(pageInfo, ResultCodeEnum.SUCCESS);
    }

    @PostMapping("save")
    public Result save(@RequestBody ProductSpec productSpec) {
        productSpecService.saveData(productSpec);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @PutMapping("updateById")
    public Result updateById(@RequestBody ProductSpec productSpec) {
        productSpecService.updateData(productSpec);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @DeleteMapping("/deleteById/{id}")
    public Result removeById(@PathVariable Long id) {
        productSpecService.deleteById(id);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("findAll")
    public Result findAll(@RequestParam Integer platformType) {
        List<ProductSpec> list = productSpecService.findAll(platformType);
        return Result.build(list, ResultCodeEnum.SUCCESS);
    }
}
