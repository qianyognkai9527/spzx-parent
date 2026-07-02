package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.MallProductPicVideoService;
import com.joker.spzx.model.dto.mall.ProductPicVideoDto;
import com.joker.spzx.model.entity.oper.MallProductPicVideo;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 商品图片表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-05-02 20:52:02
 */
@RestController
@RequestMapping("/admin/mall/productPicVideo")
public class MallProductPicvideoController {

    @Autowired
    private MallProductPicVideoService mallProductPicVideoService;

    @PostMapping("/save")
    public Result<String> savePicVideo(@RequestBody ProductPicVideoDto productPicVideoDto) {
        mallProductPicVideoService.savePicVideo(productPicVideoDto);
        return Result.build(null);
    }

    @GetMapping("/getList")
    public Result<List<MallProductPicVideo>> getPicVideo(@RequestParam Long productId, @RequestParam(required = false) Long orderId, @RequestParam Integer platformType) {
        List<MallProductPicVideo> productPicVideos = mallProductPicVideoService.getPicVideo(productId, orderId, platformType);
        return Result.build(productPicVideos);
    }

}
