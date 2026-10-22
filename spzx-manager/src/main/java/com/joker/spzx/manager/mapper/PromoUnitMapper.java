package com.joker.spzx.manager.mapper;

import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/** 推广·单元日报只读聚合。全部走 promo_cost_item_daily 明细表按 unit 聚合。 */
@Mapper
public interface PromoUnitMapper {

    List<PromoUnitVo> selectUnits(@Param("dateFrom") String dateFrom,
                                  @Param("dateTo") String dateTo,
                                  @Param("campaignId") String campaignId,
                                  @Param("sort") String sort);

    List<PromoUnitTrendVo> selectUnitTrend(@Param("dateFrom") String dateFrom,
                                           @Param("dateTo") String dateTo,
                                           @Param("campaignId") String campaignId,
                                           @Param("unitId") String unitId);

    List<PromoUnitKeywordVo> selectUnitKeywords(@Param("dateFrom") String dateFrom,
                                                @Param("dateTo") String dateTo,
                                                @Param("campaignId") String campaignId,
                                                @Param("unitId") String unitId,
                                                @Param("sort") String sort);

    List<PromoUnitCrowdVo> selectUnitCrowds(@Param("dateFrom") String dateFrom,
                                            @Param("dateTo") String dateTo,
                                            @Param("campaignId") String campaignId,
                                            @Param("unitId") String unitId);
}
