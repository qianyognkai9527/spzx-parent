package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallProductLinkService;
import com.joker.spzx.model.entity.oper.MallProductLink;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 商品和货源关系表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@RestController
@RequestMapping("/admin/mall/productLink")
public class MallProductLinkController {
    @Autowired
    private MallProductLinkService mallProductLinkService;

    public MallProductLinkController(MallProductLinkService mallProductLinkService) {
        this.mallProductLinkService = mallProductLinkService;
    }

    @GetMapping("/pageList/{pageNum}/{pageSize}")
    public Result<IPage<MallProductLink>> pageList(@PathVariable Integer pageNum,
                                                   @PathVariable Integer pageSize,
                                                   @RequestParam Integer platformType) {
        IPage<MallProductLink> page = mallProductLinkService.pageList(pageNum, pageSize, platformType);
        return Result.build(page);
    }

    @PostMapping("/saveData")
    public Result<Object> saveData(MallProductLink mallProductLink) {
        mallProductLinkService.saveData(mallProductLink);
        return Result.build(null);
    }

    @PutMapping("/updateData")
    public Result<Object> updateData(MallProductLink mallProductLink) {
        mallProductLinkService.updateData(mallProductLink);
        return Result.build(null);
    }

}
