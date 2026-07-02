package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.CategoryService;
import com.joker.spzx.model.entity.product.Category;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品分类 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Tag(description = "商品分类接口", name = "商品分类接口")
@RestController
@RequestMapping(value = "/admin/product/category")
public class CategoryController {

    @Autowired
    private CategoryService categoryService;

    @Operation(summary = "根据parentId获取下级节点")
    @GetMapping(value = "/findByParentId/{parentId}")
    public Result<List<Category>> findByParentId(@PathVariable Long parentId, @RequestParam Integer platformType) {
        List<Category> list = categoryService.findByParentId(parentId, platformType);
        return Result.build(list, ResultCodeEnum.SUCCESS);
    }
}
