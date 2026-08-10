package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.EvalGapService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.EvalGapVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/admin/mall/evalGap")
public class EvalGapController {

    @Autowired
    private EvalGapService evalGapService;

    @GetMapping("/pageList/{pageNum}/{pageSize}")
    public Result<IPage<EvalGapVo>> pageList(@PathVariable Integer pageNum,
                                             @PathVariable Integer pageSize,
                                             @RequestParam(required = false) Integer platformType,
                                             @RequestParam(required = false) String keyword,
                                             @RequestParam(required = false) String gapFilter) {
        IPage<EvalGapVo> page = evalGapService.pageList(pageNum, pageSize, platformType, keyword);
        return Result.build(page);
    }
}
