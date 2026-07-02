package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.MallProductTitleService;
import com.joker.spzx.model.entity.oper.MallProductTitle;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品历史标题表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@RestController
@RequestMapping("/admin/mall/productTitle")
public class MallProductTitleController {

    @Autowired
    private MallProductTitleService mallProductTitleService;

    @GetMapping("/list/{productId}")
    public Result<List<MallProductTitle>> pageList(@PathVariable Long productId,
                                                    @RequestParam Integer platformType) {
        List<MallProductTitle> page = mallProductTitleService.getList(productId, platformType);
        return Result.build(page);
    }

    @PostMapping("/saveData")
    public Result<String> saveData(MallProductTitle mallProductTitle) {
        mallProductTitleService.saveData(mallProductTitle);
        return Result.build(null);
    }

    @PutMapping("/updateData")
    public Result<String> updateData(MallProductTitle mallProductTitle) {
        mallProductTitleService.updateData(mallProductTitle);
        return Result.build(null);
    }

}
