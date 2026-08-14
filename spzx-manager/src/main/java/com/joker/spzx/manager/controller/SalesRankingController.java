package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.SalesRankingService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.SalesRankingVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/admin/mall/salesRanking")
public class SalesRankingController {

    @Autowired
    private SalesRankingService salesRankingService;

    @GetMapping("/ranking")
    public Result<List<SalesRankingVo>> ranking(@RequestParam(required = false) String beginTime,
                                                @RequestParam(required = false) String endTime) {
        return Result.build(salesRankingService.ranking(beginTime, endTime));
    }

    @GetMapping("/qualityRanking")
    public Result<List<SalesRankingVo>> qualityRanking(@RequestParam(required = false) String beginTime,
                                                       @RequestParam(required = false) String endTime) {
        return Result.build(salesRankingService.qualityRanking(beginTime, endTime));
    }
}
