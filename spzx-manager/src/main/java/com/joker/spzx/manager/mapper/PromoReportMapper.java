package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.promo.PromoDailyVo;
import com.joker.spzx.model.vo.promo.PromoItemVo;
import com.joker.spzx.model.vo.promo.PromoPlanVo;
import com.joker.spzx.model.vo.promo.PromoSummaryVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 推广日报只读聚合。写入方是 automation/tb-auto/collect_alimama_promo.py，这里只查不改。
 */
@Mapper
public interface PromoReportMapper {

    PromoSummaryVo selectSummary(@Param("dateFrom") String dateFrom,
                                 @Param("dateTo") String dateTo,
                                 @Param("planType") String planType);

    List<PromoDailyVo> selectTrend(@Param("dateFrom") String dateFrom,
                                   @Param("dateTo") String dateTo,
                                   @Param("planType") String planType);

    List<PromoPlanVo> selectPlans(@Param("dateFrom") String dateFrom,
                                  @Param("dateTo") String dateTo,
                                  @Param("planType") String planType);

    IPage<PromoItemVo> selectItems(IPage<PromoItemVo> page,
                                   @Param("dateFrom") String dateFrom,
                                   @Param("dateTo") String dateTo,
                                   @Param("planType") String planType,
                                   @Param("campaignId") String campaignId,
                                   @Param("keyword") String keyword,
                                   @Param("facet") String facet,
                                   @Param("sort") String sort);
}
