package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.mapper.SalesRankingMapper;
import com.joker.spzx.manager.service.SalesRankingService;
import com.joker.spzx.model.vo.mall.SalesRankingVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class SalesRankingServiceImpl implements SalesRankingService {

    @Autowired
    private SalesRankingMapper salesRankingMapper;

    @Override
    public List<SalesRankingVo> ranking(String beginTime, String endTime) {
        return salesRankingMapper.ranking(beginTime, endTime);
    }

    @Override
    public List<SalesRankingVo> qualityRanking(String beginTime, String endTime) {
        return salesRankingMapper.qualityRanking(beginTime, endTime);
    }
}
