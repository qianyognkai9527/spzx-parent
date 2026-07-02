package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.MallProductSkuService;
import com.joker.spzx.model.entity.oper.MallProductSku;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品sku表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-05-08 14:13:08
 */
@RestController
@RequestMapping("/admin/mall/productSku")
public class MallProductSkuController {

    @Autowired
    private MallProductSkuService mallProductSkuService;

    @GetMapping("/all")
    public Result<List<MallProductSku>> findAll(@RequestParam Long productId,
                                                 @RequestParam Integer platformType) {
        List<MallProductSku> list = mallProductSkuService.getList(productId, platformType);
        return Result.build(list);
    }

    @PostMapping("/save")
    public Result<List<MallProductSku>> saveData(@RequestBody MallProductSku sku) {
        mallProductSkuService.saveSku(sku);
        return Result.build(null);
    }


}
