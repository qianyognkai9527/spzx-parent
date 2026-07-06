package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.ProductBindRelationService;
import com.joker.spzx.model.dto.product.ProductBindQueryDto;
import com.joker.spzx.model.dto.product.ProductBindRelationDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品属性表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-08-22 15:59:22
 */
@RestController
@RequestMapping("/admin/mall/productBindRelation")
public class ProductBindRelationController {

    @Autowired
    private ProductBindRelationService productBindRelationService;

    @GetMapping("/findUnBindSourceProduct")
    public Result<List<Product>> findUnBindSourceProduct(ProductBindQueryDto keyword) {
        List<Product> unBindSourceProduct = productBindRelationService.findUnBindSourceProduct(keyword);
        return Result.build(unBindSourceProduct);
    }

    @PostMapping("/bindProductRelation")
    public Result<List<Product>> bindProductRelation(@RequestBody ProductBindRelationDto keyword) {
        productBindRelationService.bindRelation(keyword);
        return Result.build(null);
    }

    @GetMapping("/findBoundSourceProduct/{productId}")
    public Result<List<Product>> findBoundSourceProduct(@PathVariable Long productId) {
        List<Product> boundProducts = productBindRelationService.findBoundSourceProduct(productId);
        return Result.build(boundProducts);
    }
}
