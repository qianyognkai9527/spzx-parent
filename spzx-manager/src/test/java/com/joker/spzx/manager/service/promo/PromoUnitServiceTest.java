package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 单元日报的纯函数：占比先加总再除（分子分母在 SQL 已汇总好）、分母 0 出 null、
 * 缺省区间止于昨天。纯 JUnit，不拉 Spring。
 */
class PromoUnitServiceTest {

    @Test
    void 人群占比先加总再除且分母为0出null() {
        PromoUnitVo v = new PromoUnitVo();
        v.setClick(10L);
        v.setCrowdClick(3L);
        PromoUnitService.applyCrowdShare(v);
        assertEquals(0, new java.math.BigDecimal("30.00").compareTo(v.getCrowdClickShare()));
        v.setClick(0L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
    }

    @Test
    void 人群占比分子或分母缺失出null() {
        PromoUnitVo v = new PromoUnitVo();
        v.setClick(10L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
        v.setClick(null);
        v.setCrowdClick(3L);
        PromoUnitService.applyCrowdShare(v);
        assertNull(v.getCrowdClickShare());
    }

    @Test
    void 趋势行占比同口径() {
        PromoUnitTrendVo t = new PromoUnitTrendVo();
        t.setClick(8L);
        t.setCrowdClick(5L);
        PromoUnitService.applyTrendShare(t);
        assertEquals(0, new java.math.BigDecimal("62.50").compareTo(t.getCrowdClickShare()));
    }

    @Test
    void 人群行占比按单元总点击算且总点击缺失出null() {
        PromoUnitCrowdVo c = new PromoUnitCrowdVo();
        c.setClick(3L);
        c.setUnitClick(10L);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertEquals(0, new java.math.BigDecimal("30.00").compareTo(c.getCrowdClickShare()));
        c.setUnitClick(0L);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertNull(c.getCrowdClickShare());
        c.setUnitClick(null);
        PromoUnitService.applyCrowdShareToUnitClick(c);
        assertNull(c.getCrowdClickShare());
    }

    @Test
    void 缺省区间止于昨天而不是今天() {
        String[] r = PromoReportService.normalizeRange(null, null, LocalDate.of(2026, 10, 18));
        assertEquals("2026-10-04", r[0]);
        assertEquals("2026-10-17", r[1]);
    }
}
