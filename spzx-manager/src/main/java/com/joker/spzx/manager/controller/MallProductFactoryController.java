package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallProductFactoryService;
import com.joker.spzx.model.dto.product.ProductFactoryPageParam;
import com.joker.spzx.model.entity.oper.MallProductFactory;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 工厂基本信息表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@RestController
@RequestMapping("/admin/mall/productFactory")
public class MallProductFactoryController {

    private final MallProductFactoryService mallProductFactoryService;

    public MallProductFactoryController(MallProductFactoryService mallProductFactoryService) {
        this.mallProductFactoryService = mallProductFactoryService;
    }

    @GetMapping("/pageList")
    public Result<IPage<MallProductFactory>> pageList(ProductFactoryPageParam pageParam) {
        IPage<MallProductFactory> page = mallProductFactoryService.pageList(pageParam);
        return Result.build(page);
    }

    @PostMapping("/saveData")
    public Result<String> saveData(@RequestBody MallProductFactory mallProductFactory) {
        mallProductFactoryService.saveData(mallProductFactory);
        return Result.build("保存成功");
    }

    @PutMapping("/updateData")
    public Result<String> updateData(@RequestBody MallProductFactory mallProductFactory) {
        mallProductFactoryService.updateData(mallProductFactory);
        return Result.build("修改成功");
    }

    @GetMapping("/allProductFactory")
    public Result<List<MallProductFactory>> getAllData(@RequestParam(required = false) Integer platformType) {
        List<MallProductFactory> list = mallProductFactoryService.getAllProductFactory(platformType);
        return Result.build(list);
    }

    @GetMapping("/getDetail")
    public Result<MallProductFactory> getDetail(@RequestParam Long id) {
        MallProductFactory factory = mallProductFactoryService.getById(id);
        return Result.build(factory);
    }

    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@PathVariable Long id) {
        mallProductFactoryService.deleteById(id);
        return Result.build("删除成功");
    }
}
