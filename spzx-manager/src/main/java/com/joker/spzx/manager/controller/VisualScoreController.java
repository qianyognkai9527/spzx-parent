package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.VisualScoreService;
import com.joker.spzx.model.dto.mall.GenerateVariantDto;
import com.joker.spzx.model.dto.mall.RescoreDto;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.VisualScoreSourceVo;
import com.joker.spzx.model.vo.mall.VisualScoreStatsVo;
import com.joker.spzx.model.vo.mall.VisualScoreVo;
import com.joker.spzx.model.vo.mall.VariantSetVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin/mall/visualScore")
public class VisualScoreController {

    @Autowired
    private VisualScoreService visualScoreService;

    @GetMapping("/platform/pageList/{pageNum}/{pageSize}")
    public Result<IPage<VisualScoreVo>> platformPageList(@PathVariable Integer pageNum,
                                                          @PathVariable Integer pageSize,
                                                          @RequestParam(required = false) Integer platformType,
                                                          @RequestParam(required = false) String keyword,
                                                          @RequestParam(required = false) Integer scoreMin,
                                                          @RequestParam(required = false) Integer scoreMax) {
        return Result.build(visualScoreService.pageListPlatform(pageNum, pageSize, platformType, keyword, scoreMin, scoreMax));
    }

    @GetMapping("/source/pageList/{pageNum}/{pageSize}")
    public Result<IPage<VisualScoreSourceVo>> sourcePageList(@PathVariable Integer pageNum,
                                                              @PathVariable Integer pageSize,
                                                              @RequestParam(required = false) String keyword,
                                                              @RequestParam(required = false) Integer scoreMin,
                                                              @RequestParam(required = false) Integer scoreMax) {
        return Result.build(visualScoreService.pageListSource(pageNum, pageSize, keyword, scoreMin, scoreMax));
    }

    @GetMapping("/platform/stats")
    public Result<VisualScoreStatsVo> platformStats(@RequestParam(required = false) Integer platformType) {
        return Result.build(visualScoreService.statsPlatform(platformType));
    }

    @GetMapping("/source/stats")
    public Result<VisualScoreStatsVo> sourceStats() {
        return Result.build(visualScoreService.statsSource());
    }

    @PostMapping("/rescore")
    public Result<Integer> rescore(@RequestBody RescoreDto dto) {
        return Result.build(visualScoreService.rescore(dto));
    }

    @PostMapping("/generateVariant")
    public Result<Integer> generateVariant(@RequestBody GenerateVariantDto dto) {
        return Result.build(visualScoreService.generateVariant(dto));
    }

    @GetMapping("/variantList")
    public Result<List<VariantSetVo>> variantList(@RequestParam Long productId,
                                                  @RequestParam(required = false) Integer platformType) {
        return Result.build(visualScoreService.variantList(productId, platformType));
    }
}
