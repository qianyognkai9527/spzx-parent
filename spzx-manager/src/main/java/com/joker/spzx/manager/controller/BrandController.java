package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.BrandService;
import com.joker.spzx.model.entity.product.Brand;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 分类品牌 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:06:15
 */
@RestController
@Tag(description = "品牌管理", name = "品牌管理")
@RequestMapping(value = "/admin/product/brand")
public class BrandController {
    @Autowired
    private BrandService brandService;

    @Operation(summary = "分页查询")
    @GetMapping("/{page}/{limit}")
    public Result<IPage<Brand>> findByPage(@PathVariable Integer page, @PathVariable Integer limit,
                                           @RequestParam Integer platformType) {
        IPage<Brand> pageInfo = brandService.findByPage(page, limit, platformType);
        return Result.build(pageInfo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/findAll")
    public Result findAll(@RequestParam Integer platformType) {
        List<Brand> list = brandService.findAll(platformType);
        return Result.build(list);
    }

}
