package com.joker.spzx.manager.service.kw;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 关键词推广（标准计划）出价链条的算术 —— 纯函数，不拉 Spring、不联网。
 *
 * 链条：关键词出价 → ×(1+人群溢价) → ×分时折扣 → 全能调价再乘一个平台自动系数。
 * 两件必须靠测试钉死的事：
 *  1. 人群溢价**取最高、不叠加**（叠起来会把上限虚高一截，反推出来的出价就敢乱花）；
 *  2. 全能调价是黑箱，只公开幅度 ⇒ 只允许给**区间**，且反推上限必须用最坏情况（+幅度）。
 */
class KwBidCalculatorTest {

    private static void eq(String what, double expected, double actual) {
        assertEquals(expected, actual, 0.0001, what + " 应为 " + expected + "，实际 " + actual);
    }

    @Test
    void 溢价和折扣按顺序连乘() {
        // 1.00 ×(1+30%) = 1.30，再 ×120% = 1.56
        eq("命中人群后的出价", 1.30, KwBidCalculator.withPremium(1.00, 30));
        eq("再乘分时折扣", 1.56, KwBidCalculator.withDiscount(1.30, 120));
        eq("整条链", 1.56, KwBidCalculator.finalBid(1.00, 30, 120));
    }

    @Test
    void 多人群命中取最高溢价而不是相加() {
        List<KwBidCalculator.Crowd> crowds = List.of(
                new KwBidCalculator.Crowd("智能拉新", 15),
                new KwBidCalculator.Crowd("收藏加购", 40),
                new KwBidCalculator.Crowd("同行偏好", 25));
        eq("取最高", 40, KwBidCalculator.highestPremium(crowds));
        // 常见错法：15+40+25=80% → 1.80；正确是 1.40
        eq("出价不该是叠加结果", 1.40, KwBidCalculator.finalBid(1.00, KwBidCalculator.highestPremium(crowds), 100));
        eq("空人群不打折", 0, KwBidCalculator.highestPremium(List.of()));
    }

    @Test
    void 分时折扣为零表示该时段不投放() {
        eq("凌晨 0% 出价归零", 0.0, KwBidCalculator.withDiscount(1.56, 0));
        assertTrue(KwBidCalculator.notServing(0));
        assertFalse(KwBidCalculator.notServing(30));
    }

    @Test
    void 全能调价只给区间不给点值() {
        double bid = 2.00;
        eq("上沿", 2.60, KwBidCalculator.omniHigh(bid, 30));
        eq("下沿", 1.40, KwBidCalculator.omniLow(bid, 30));
        eq("幅度 0 时区间退化为点", 2.00, KwBidCalculator.omniLow(bid, 0));
        // 幅度 100% 时下沿不能变成负数
        eq("下沿不为负", 0.0, KwBidCalculator.omniLow(bid, 100));
    }

    @Test
    void 扣费上限等于当时的最终出价() {
        // GSP：扣费 = 对手出价×对手质量分/我的质量分 + 0.01，且不超过我的出价
        // 质量分高的一方受益：对手 1.00×8 分、我 10 分 → 0.80 + 0.01
        eq("第二价加一分", 0.81, KwBidCalculator.gspCharge(1.00, 8, 10, 5.00));
        eq("算出来比出价高时按出价收", 1.10, KwBidCalculator.gspCharge(3.00, 10, 8, 1.10));
        eq("出价 0 不收钱", 0.0, KwBidCalculator.gspCharge(3.00, 10, 8, 0));
        eq("同质量分加一分后超过出价，仍按出价收", 2.00, KwBidCalculator.gspCharge(2.00, 10, 10, 2.00));
    }

    @Test
    void 可承受cpc按费率与按毛利分成两种口径() {
        // 客单价 60、转化率 4%、可承受推广费率 20% → 每单 12 元 × 4% = 0.48
        eq("费率口径", 0.48, KwBidCalculator.cpcCeilingByFeeRate(60, 4, 20));
        // 每单毛利 25、愿意拿 40% 毛利投推广 → 每单 10 元 × 4% = 0.40
        eq("毛利分成口径", 0.40, KwBidCalculator.cpcCeilingByMargin(25, 4, 40));
        eq("转化率为 0 时上限为 0", 0.0, KwBidCalculator.cpcCeilingByFeeRate(60, 0, 20));
    }

    @Test
    void 反推关键词出价用最坏情况() {
        // CPC 上限 0.48，人群溢价 30%、分时 120%、全能 +30% 全叠满
        // 0.48 / (1.3 × 1.2 × 1.3) = 0.2367
        eq("最坏情况下可出的基数", 0.2367, KwBidCalculator.maxBaseBid(0.48, 30, 120, 30));
        // 不看全能调价（幅度 0）：0.48 / (1.3 × 1.2) = 0.3077
        eq("幅度为 0 时可出更高", 0.3077, KwBidCalculator.maxBaseBid(0.48, 30, 120, 0));
        // 该时段不投放时，基数无论多高出价都是 0 —— 反推不能给出一个正数
        eq("折扣 0 反推给 0", 0.0, KwBidCalculator.maxBaseBid(0.48, 30, 0, 30));
        eq("溢价 0 也照常反推", 0.4, KwBidCalculator.maxBaseBid(0.48, 0, 120, 0));
    }

    @Test
    void 正反两向必须自洽() {
        double base = 1.35;
        double premium = 25, discount = 110, swing = 30;
        double ceiling = KwBidCalculator.omniHigh(KwBidCalculator.finalBid(base, premium, discount), swing);
        eq("反推再正算回到上限", ceiling,
                KwBidCalculator.omniHigh(KwBidCalculator.finalBid(
                        KwBidCalculator.maxBaseBid(ceiling, premium, discount, swing), premium, discount), swing));
    }

    @Test
    void 矩阵按人群乘时段铺开且能找出全局最高出价() {
        var matrix = KwBidCalculator.matrix(1.00,
                List.of(new KwBidCalculator.Crowd("A", 20), new KwBidCalculator.Crowd("B", 50)),
                List.of(new KwBidCalculator.Schedule("00-07", 0), new KwBidCalculator.Schedule("08-23", 100)),
                30);
        eq("格子数 = 人群×时段", 4, matrix.cells().size());
        var b0823 = matrix.cells().stream()
                .filter(c -> c.crowd().equals("B") && c.schedule().equals("08-23")).findFirst().orElseThrow();
        eq("B 人群白天确定值", 1.50, b0823.certain());
        eq("B 人群白天区间上沿", 1.95, b0823.high());
        var a0007 = matrix.cells().stream()
                .filter(c -> c.crowd().equals("A") && c.schedule().equals("00-07")).findFirst().orElseThrow();
        assertTrue(a0007.notServing(), "凌晨折扣 0 应标记为不投放");
        eq("全局最高出价取 B×白天×+30%", 1.95, matrix.maxHigh());
    }

    @Test
    void 非法输入必须当场报错而不是算出负出价() {
        assertThrows(IllegalArgumentException.class, () -> KwBidCalculator.withPremium(1.0, -1));
        assertThrows(IllegalArgumentException.class, () -> KwBidCalculator.withDiscount(1.0, 301));
        assertThrows(IllegalArgumentException.class, () -> KwBidCalculator.omniHigh(1.0, 101));
        assertThrows(IllegalArgumentException.class, () -> KwBidCalculator.cpcCeilingByFeeRate(-60, 4, 20));
        // NaN/Infinity 也要挡住：前端传上来会变成一堆 NaN
        assertThrows(IllegalArgumentException.class, () -> KwBidCalculator.finalBid(Double.NaN, 30, 100));
    }

    @Test
    void 宝贝带入用成交均价而不是标价() {
        // 近7日：成交 1200 元 / 20 个买家 / 800 访客 → 客单价 60、转化率 2.5%
        var t = KwBidCalculator.targetFromItem(
                new KwBidCalculator.ItemInputs(1200, 20, 800, 18.5, false));
        eq("客单价取成交均价", 60.0, t.unitPrice());
        eq("转化率=买家/访客", 2.5, t.convRatePct());
        eq("每单毛利原样带过来", 18.5, t.unitMargin());
        // 标价 199 时按标价算会把上限抬到 3.3 倍，所以绝不退回标价
        assertTrue(t.unitPrice() < 199, "客单价不该用标价");
    }

    @Test
    void 异常流量宝贝与零访客宝贝都拒绝带入() {
        IllegalArgumentException abn = assertThrows(IllegalArgumentException.class, () ->
                KwBidCalculator.targetFromItem(new KwBidCalculator.ItemInputs(0, 0, 1500, 18.5, true)));
        assertTrue(abn.getMessage().contains("低质流量"), "要说清为什么不能用：" + abn.getMessage());
        IllegalArgumentException none = assertThrows(IllegalArgumentException.class, () ->
                KwBidCalculator.targetFromItem(new KwBidCalculator.ItemInputs(0, 0, 0, 18.5, false)));
        assertTrue(none.getMessage().contains("没有访客数据"), "要区分“没采到”和“采到 0”：" + none.getMessage());
    }

    @Test
    void 有访客但零成交时转化率与上限都是零() {
        var t = KwBidCalculator.targetFromItem(new KwBidCalculator.ItemInputs(0, 0, 320, 18.5, false));
        eq("零成交转化率 0", 0.0, t.convRatePct());
        eq("零成交客单价 0", 0.0, t.unitPrice());
        eq("据此反推的上限也是 0", 0.0, KwBidCalculator.cpcCeilingByMargin(t.unitMargin(), t.convRatePct(), 40));
    }

    @Test
    void 金额一律两位小数且向下取整不吹上限() {
        eq("出价向下到分", 1.87, KwBidCalculator.money(1.872));
        eq("上限也向下取整（不吹）", 1.49, KwBidCalculator.money(1.4999));
        eq("零保持零", 0.0, KwBidCalculator.money(0));
    }
}
