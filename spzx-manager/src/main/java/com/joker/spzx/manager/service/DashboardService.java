package com.joker.spzx.manager.service;

import com.joker.spzx.model.vo.dashboard.*;

import java.util.List;

/**
 * 仪表盘服务
 *
 * @author joker
 */
public interface DashboardService {

    DashboardKpiVo getKpiCards();

    List<OrderTrendVo> getOrderTrend();

    List<PlatformDistVo> getPlatformDistribution();

    List<TopFactoryVo> getTopFactories();

    List<RecentLogVo> getRecentLogs();
}
