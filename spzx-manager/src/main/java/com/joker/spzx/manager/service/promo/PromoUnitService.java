package com.joker.spzx.manager.service.promo;

import com.joker.spzx.manager.mapper.PromoUnitMapper;
import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;

/**
 * 推广·单元日报（只读下钻，spec 2026-10-18-promo-unit-daily-design）。
 *
 * 占比公式全服务只有 pct() 这一份：分子分母都已在 SQL 里按区间汇总好，这里只做除法 ——
 * 「先加总再除」「分母 0 出 NULL 不粉饰成 0」与 PromoReportService.applyCrowdShare 同一条纪律，
 * 但作用在不同 VO 上，各自有单测钉住。
 */
@Service
public class PromoUnitService {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    @Autowired
    private PromoUnitMapper promoUnitMapper;

    public List<PromoUnitVo> units(String from, String to, String campaignId, String sort) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitVo> list = promoUnitMapper.selectUnits(r[0], r[1], campaignId.trim(), sort);
        list.forEach(PromoUnitService::applyCrowdShare);
        return list;
    }

    public List<PromoUnitTrendVo> trend(String from, String to, String campaignId, String unitId) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitTrendVo> list =
                promoUnitMapper.selectUnitTrend(r[0], r[1], campaignId.trim(), unitId.trim());
        list.forEach(PromoUnitService::applyTrendShare);
        return list;
    }

    public List<PromoUnitKeywordVo> keywords(String from, String to, String campaignId, String unitId,
                                             String sort) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        return promoUnitMapper.selectUnitKeywords(r[0], r[1], campaignId.trim(), unitId.trim(), sort);
    }

    public List<PromoUnitCrowdVo> crowds(String from, String to, String campaignId, String unitId) {
        String[] r = PromoReportService.normalizeRange(from, to, LocalDate.now());
        List<PromoUnitCrowdVo> list =
                promoUnitMapper.selectUnitCrowds(r[0], r[1], campaignId.trim(), unitId.trim());
        list.forEach(PromoUnitService::applyCrowdShareToUnitClick);
        return list;
    }

    static void applyCrowdShare(PromoUnitVo vo) {
        vo.setCrowdClickShare(pct(vo.getCrowdClick(), vo.getClick()));
    }

    static void applyTrendShare(PromoUnitTrendVo vo) {
        vo.setCrowdClickShare(pct(vo.getCrowdClick(), vo.getClick()));
    }

    static void applyCrowdShareToUnitClick(PromoUnitCrowdVo vo) {
        vo.setCrowdClickShare(pct(vo.getClick(), vo.getUnitClick()));
    }

    private static BigDecimal pct(Long num, Long den) {
        if (num == null || den == null || den == 0) {
            return null;
        }
        return BigDecimal.valueOf(num).multiply(HUNDRED)
                .divide(BigDecimal.valueOf(den), 2, RoundingMode.HALF_UP);
    }
}
