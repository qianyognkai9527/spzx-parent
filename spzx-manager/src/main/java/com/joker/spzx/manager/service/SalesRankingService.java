package com.joker.spzx.manager.service;

import com.joker.spzx.model.vo.mall.SalesRankingVo;

import java.util.List;

public interface SalesRankingService {

    List<SalesRankingVo> ranking(String beginTime, String endTime);

    List<SalesRankingVo> qualityRanking(String beginTime, String endTime);
}
