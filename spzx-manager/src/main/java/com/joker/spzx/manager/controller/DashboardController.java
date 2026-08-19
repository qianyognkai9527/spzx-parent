package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.DashboardService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.dashboard.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 仪表盘控制器
 *
 * @author joker
 */
@RestController
@RequestMapping(value = "/admin/dashboard")
public class DashboardController {

    @Autowired
    private DashboardService dashboardService;

    @GetMapping("/kpi")
    public Result<DashboardKpiVo> getKpiCards() {
        return Result.build(dashboardService.getKpiCards(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/orderTrend")
    public Result<List<OrderTrendVo>> getOrderTrend() {
        return Result.build(dashboardService.getOrderTrend(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/platformDist")
    public Result<List<PlatformDistVo>> getPlatformDistribution() {
        return Result.build(dashboardService.getPlatformDistribution(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/topFactories")
    public Result<List<TopFactoryVo>> getTopFactories() {
        return Result.build(dashboardService.getTopFactories(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/recentLogs")
    public Result<List<RecentLogVo>> getRecentLogs() {
        return Result.build(dashboardService.getRecentLogs(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/watermarkProducts")
    public Result<java.util.List<java.util.Map<String, Object>>> getWatermarkProducts() {
        return Result.build(dashboardService.getWatermarkProducts(), ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/taskAnomalies")
    public Result<java.util.List<java.util.Map<String, Object>>> getTaskAnomalies() {
        return Result.build(dashboardService.getTaskAnomalies(), ResultCodeEnum.SUCCESS);
    }
}
