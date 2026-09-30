package com.joker.spzx.manager.service.impl;

import com.joker.spzx.model.vo.dashboard.DashboardKpiVo;
import com.joker.spzx.model.vo.dashboard.EffectTrendVo;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DashboardKpiBuildTest {

    private static EffectTrendVo snapshot(String time, int items, long visitors, String payAmount, long cartUsers) {
        EffectTrendVo vo = new EffectTrendVo();
        vo.setSnapshotTime(time);
        vo.setItems(items);
        vo.setVisitors(visitors);
        vo.setPayAmount(new BigDecimal(payAmount));
        vo.setCartUsers(cartUsers);
        return vo;
    }

    /** mapper 返回倒序：index 0 是最新一次快照 */
    private static List<EffectTrendVo> twoSnapshots() {
        return Arrays.asList(
                snapshot("2026-09-30 06:03", 290, 14966, "0.00", 1),
                snapshot("2026-09-27 06:02", 282, 13200, "302.74", 8));
    }

    @Test
    void 取最新快照作为当前指标() {
        DashboardKpiVo vo = DashboardServiceImpl.buildKpi(twoSnapshots(), 1299L, 4689L, 4679L, 3L,
                new BigDecimal("4504.87"), 99L);
        assertEquals("2026-09-30 06:03", vo.getSnapshotAt());
        assertEquals(290, vo.getEffectItems());
        assertEquals(14966L, vo.getVisitors7d());
        assertEquals(new BigDecimal("0.00"), vo.getPayAmount7d());
        assertEquals(1L, vo.getCartUsers7d());
    }

    @Test
    void 有上一份快照时带出环比基数() {
        DashboardKpiVo vo = DashboardServiceImpl.buildKpi(twoSnapshots(), 1L, 1L, 1L, 0L,
                BigDecimal.ZERO, 0L);
        assertEquals(13200L, vo.getVisitorsPrev7d());
        assertEquals(new BigDecimal("302.74"), vo.getPayAmountPrev7d());
    }

    @Test
    void 只有一份快照时没有环比基数() {
        DashboardKpiVo vo = DashboardServiceImpl.buildKpi(
                Collections.singletonList(snapshot("2026-09-30 06:03", 290, 14966, "0.00", 1)),
                1L, 1L, 1L, 0L, BigDecimal.ZERO, 0L);
        assertNull(vo.getVisitorsPrev7d());
        assertNull(vo.getPayAmountPrev7d());
    }

    @Test
    void 没有快照时经营指标为null而不是0() {
        // 显示 0 会被读成"今天一单没出"，而真相是生意参谋还没采过
        for (List<EffectTrendVo> empty : Arrays.<List<EffectTrendVo>>asList(Collections.emptyList(), new ArrayList<>())) {
            DashboardKpiVo vo = DashboardServiceImpl.buildKpi(empty, 1299L, 4689L, 4679L, 5L,
                    new BigDecimal("4504.87"), 99L);
            assertNull(vo.getSnapshotAt());
            assertNull(vo.getVisitors7d());
            assertNull(vo.getPayAmount7d());
            assertNull(vo.getCartUsers7d());
            assertNull(vo.getEffectItems());
            // 与效果数据无关的口径照常给出
            assertEquals(1299L, vo.getFactoryCount());
            assertEquals(4689L, vo.getProductCount());
            assertEquals(4679L, vo.getPlatformProductCount());
            assertEquals(5L, vo.getUnreadAlerts());
            assertEquals(new BigDecimal("4504.87"), vo.getMonthExpense());
        }
    }

    @Test
    void 入参null快照列表不抛异常() {
        DashboardKpiVo vo = DashboardServiceImpl.buildKpi(null, 1L, 1L, 1L, 1L, BigDecimal.ONE, 1L);
        assertNull(vo.getSnapshotAt());
        assertEquals(BigDecimal.ONE, vo.getMonthExpense());
    }

    @Test
    void 趋势序列按时间正序返回() {
        List<EffectTrendVo> asc = DashboardServiceImpl.toChronological(twoSnapshots());
        assertEquals("2026-09-27 06:02", asc.get(0).getSnapshotTime());
        assertEquals("2026-09-30 06:03", asc.get(1).getSnapshotTime());
    }

    @Test
    void 没有快照时趋势是空列表而不是null() {
        assertTrue(DashboardServiceImpl.toChronological(null).isEmpty());
        assertTrue(DashboardServiceImpl.toChronological(Collections.emptyList()).isEmpty());
    }
}
