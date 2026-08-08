package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.mapper.DashboardMapper;
import com.joker.spzx.manager.service.DashboardService;
import com.joker.spzx.model.vo.dashboard.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 仪表盘服务实现
 *
 * @author joker
 */
@Service
public class DashboardServiceImpl implements DashboardService {

    @Autowired
    private DashboardMapper dashboardMapper;

    @Override
    public DashboardKpiVo getKpiCards() {
        DashboardKpiVo vo = new DashboardKpiVo();
        vo.setOrderCount(dashboardMapper.countOrders());
        vo.setOrderTotalAmount(dashboardMapper.sumOrderAmount());
        vo.setFactoryCount(dashboardMapper.countFactories());
        vo.setProductCount(dashboardMapper.countProducts());
        return vo;
    }

    @Override
    public List<OrderTrendVo> getOrderTrend() {
        return dashboardMapper.selectOrderTrend();
    }

    @Override
    public List<PlatformDistVo> getPlatformDistribution() {
        List<PlatformDistVo> list = dashboardMapper.selectPlatformDist();
        for (PlatformDistVo vo : list) {
            if (vo.getPlatformType() != null && vo.getPlatformType() == 1) {
                vo.setPlatformName("淘宝");
            } else if (vo.getPlatformType() != null && vo.getPlatformType() == 2) {
                vo.setPlatformName("抖音");
            } else {
                vo.setPlatformName("未分类");
            }
        }
        return list;
    }

    @Override
    public List<TopFactoryVo> getTopFactories() {
        return dashboardMapper.selectTopFactories();
    }

    @Override
    public List<RecentLogVo> getRecentLogs() {
        return dashboardMapper.selectRecentLogs();
    }
}
