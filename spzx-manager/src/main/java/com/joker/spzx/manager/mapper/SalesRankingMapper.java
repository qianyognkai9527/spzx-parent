package com.joker.spzx.manager.mapper;

import com.joker.spzx.model.vo.mall.SalesRankingVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface SalesRankingMapper {

    List<SalesRankingVo> ranking(@Param("beginTime") String beginTime,
                                 @Param("endTime") String endTime);

    List<SalesRankingVo> qualityRanking(@Param("beginTime") String beginTime,
                                        @Param("endTime") String endTime);
}
