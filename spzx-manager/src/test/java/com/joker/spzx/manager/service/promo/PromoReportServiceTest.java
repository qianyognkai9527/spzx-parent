package com.joker.spzx.manager.service.promo;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 区间收敛与白名单归一 —— 纯函数，不拉 Spring。
 *
 * 守的是两件真实会错事：
 * 1) 默认区间把"今天"放进去。采集器只取昨天及更早（当天未结算），
 *    带今天就等于让看板显示"今天花费 0"，而真相是"今天还没采"。
 * 2) 非法 facet/sort 直接进 SQL 的 <choose>，拼错一个字母就整页空。
 */
class PromoReportServiceTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 3);

    @Test
    void 缺省区间止于昨天而不是今天() {
        String[] r = PromoReportService.normalizeRange(null, null, TODAY);
        assertEquals("2026-09-19", r[0]);
        assertEquals("2026-10-02", r[1]);   // 昨天，不是 10-03
    }

    @Test
    void 只给止日期时往前推十四天() {
        String[] r = PromoReportService.normalizeRange(null, "2026-10-01", TODAY);
        assertEquals("2026-09-18", r[0]);
        assertEquals("2026-10-01", r[1]);
    }

    @Test
    void 起止颠倒自动交换而不是报错() {
        String[] r = PromoReportService.normalizeRange("2026-10-01", "2026-09-20", TODAY);
        // 两端都是显式传的，交换后原样保留，不能被默认窗口改写
        assertEquals("2026-09-20", r[0]);
        assertEquals("2026-10-01", r[1]);
    }

    @Test
    void 未来日期被夹到今天() {
        String[] r = PromoReportService.normalizeRange("2026-10-01", "2026-12-31", TODAY);
        assertEquals("2026-10-01", r[0]);
        assertEquals("2026-10-03", r[1]);
    }

    @Test
    void 超上限从起点截而不是把整页打空() {
        String[] r = PromoReportService.normalizeRange("2020-01-01", "2026-10-02", TODAY);
        assertEquals("2026-07-05", r[0]);   // 90 天闭窗口
        assertEquals("2026-10-02", r[1]);
    }

    @Test
    void 坏日期退回默认而不是抛异常() {
        // 两端都坏：斜杠日期只按 ISO 解析，这里当作非法值，两端一起退回默认窗口
        String[] r = PromoReportService.normalizeRange("2026/10/01", "not-a-date", TODAY);
        assertEquals("2026-09-19", r[0]);
        assertEquals("2026-10-02", r[1]);
        // 只有一端坏：另一端是显式传的有效日期，必须保留，不能被默认窗口改写
        String[] keep = PromoReportService.normalizeRange("2026-10-01", null, TODAY);
        assertEquals("2026-10-01", keep[0]);
        assertEquals("2026-10-02", keep[1]);
        assertNull(PromoReportService.parseDate(""));
        assertNull(PromoReportService.parseDate(null));
        assertNull(PromoReportService.parseDate("2026-13-45"));
        assertEquals(LocalDate.of(2026, 9, 3), PromoReportService.parseDate(" 2026-09-03 "));
    }

    @Test
    void 非法枚举值退回白名单默认() {
        assertEquals("noDeal", PromoReportService.normalizeChoice(
                "  noDeal  ", java.util.Set.of("all", "noDeal"), "all"));
        assertEquals("all", PromoReportService.normalizeChoice(
                "no_deal", java.util.Set.of("all", "noDeal"), "all"));
        assertEquals("all", PromoReportService.normalizeChoice(
                null, java.util.Set.of("all", "noDeal"), "all"));
        assertEquals("keyword", PromoReportService.normalizeChoice(
                "keyword", java.util.Set.of("all", "keyword"), "all"));
        assertEquals("all", PromoReportService.normalizeChoice(
                "'; DROP TABLE", java.util.Set.of("all", "keyword"), "all"));
    }
}
