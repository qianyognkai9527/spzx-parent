package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.vo.promo.PromoItemVo;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 推广费进毛利的算术 —— 纯函数，不拉 Spring。
 *
 * 守的三件真会算错事：
 * 1) 「没出货」和「算不出」是两回事。库里现在 215 个投了钱的宝贝成交全是 0，
 *    这时净利就是 −花费（真实亏损），不能因为缺进价就整列变 null——那会把"烧钱不出单"
 *    这个最该看见的信号抹掉。
 * 2) 出货了但原料缺失必须 null 而不是 0：把"不知道进价"记成"进价 0"等于凭空造出利润。
 * 3) 净利不含运费。商品运营台的 margin 也不含，两处一旦一个含一个不含，
 *    同一个宝贝在两个页面上的毛利就对不上，而没人会去核对第二处。
 */
class PromoProfitMathTest {

    private static PromoItemVo row(String gmv, Integer units, String charge,
                                   String sourcePrice, String commission, String payFee,
                                   String freight) {
        PromoItemVo vo = new PromoItemVo();
        vo.setGmvTotal(gmv == null ? null : new BigDecimal(gmv));
        vo.setOrderTotal(units);
        vo.setCharge(charge == null ? null : new BigDecimal(charge));
        vo.setSourcePrice(sourcePrice == null ? null : new BigDecimal(sourcePrice));
        vo.setCommissionRate(commission == null ? null : new BigDecimal(commission));
        vo.setPaymentFeeRate(payFee == null ? null : new BigDecimal(payFee));
        vo.setFreight(freight == null ? null : new BigDecimal(freight));
        return vo;
    }

    private static void assertMoney(String expected, BigDecimal actual) {
        assertMoney(expected, actual, null);
    }

    private static void assertMoney(String expected, BigDecimal actual, String message) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual),
                (message == null ? "" : message + "，") + "期望 " + expected + " 实际 " + actual);
    }

    @Test
    void 零成交的宝贝净利就是负花费() {
        // 实测形状：853044770497 花 38.14、0 成交、也没绑货源（进价 null）
        PromoItemVo vo = row("0.00", 0, "38.14", null, "4.00", "0.600", null);
        PromoReportService.applyProfit(vo);
        assertMoney("0.00", vo.getGoodsCost());
        assertMoney("0.00", vo.getPlatformFee());
        assertMoney("-38.14", vo.getNetProfit());
        assertNull(vo.getProfitGaps(), "没出货不该报缺项");
        assertMoney("-1.00", vo.getNetRoi());
    }

    @Test
    void 出货且原料齐按笔数计货成本与费率() {
        // 成交 100 / 2 笔 / 进价 30 / 费率 4%+0.6% / 花费 20
        PromoItemVo vo = row("100.00", 2, "20.00", "30.00", "4.00", "0.600", null);
        PromoReportService.applyProfit(vo);
        assertMoney("60.00", vo.getGoodsCost());
        assertMoney("4.60", vo.getPlatformFee());
        assertMoney("15.40", vo.getNetProfit());
        assertMoney("0.77", vo.getNetRoi());
        assertNull(vo.getProfitGaps());
    }

    @Test
    void 出货缺进价判不可算而不是进价零() {
        PromoItemVo vo = row("100.00", 1, "20.00", null, "4.00", "0.600", null);
        PromoReportService.applyProfit(vo);
        assertNull(vo.getGoodsCost());
        assertNull(vo.getNetProfit(), "不知道进价就不能出净利，出了就是假盈利");
        assertNull(vo.getNetRoi());
        assertEquals("缺进价", vo.getProfitGaps());
    }

    @Test
    void 两个原料都缺时缺口并列() {
        PromoItemVo vo = row("100.00", 1, "20.00", null, null, null, "5.00");
        PromoReportService.applyProfit(vo);
        assertEquals("缺进价、缺费率", vo.getProfitGaps());
        assertNull(vo.getNetProfit());
    }

    @Test
    void 运费单列且不参与净利() {
        PromoItemVo with = row("100.00", 2, "20.00", "30.00", "4.00", "0.600", "5.00");
        PromoReportService.applyProfit(with);
        assertMoney("10.00", with.getFreightCost());
        assertMoney("15.40", with.getNetProfit(), "运费进不进净利要唯一，这里不含");

        PromoItemVo without = row("100.00", 2, "20.00", "30.00", "4.00", "0.600", null);
        PromoReportService.applyProfit(without);
        assertMoney("0.00", without.getFreightCost());
        assertMoney("15.40", without.getNetProfit(), "缺运费不能让净利变 null，也不能被偷偷扣掉");
    }

    @Test
    void 花费为零时ROI出空而不是零或除零() {
        PromoItemVo vo = row("100.00", 2, "0.00", "30.00", "4.00", "0.600", null);
        PromoReportService.applyProfit(vo);
        assertMoney("35.40", vo.getNetProfit());    // 100 − 60 − 4.60 − 0
        assertNull(vo.getNetRoi(), "分母 0 的比率没有意义，0 会被读成「白烧」");
    }

    @Test
    void 金额按四舍五入而不是银行家舍入() {
        // 33.33 × 4.6% = 1.53318 → 1.53；Java 的 Math.round/BigDecimal.ROUND_HALF_UP 一致
        PromoItemVo vo = row("33.33", 1, "0.00", "1.00", "4.00", "0.600", null);
        PromoReportService.applyProfit(vo);
        assertMoney("1.53", vo.getPlatformFee());
        assertMoney("30.80", vo.getNetProfit());    // 33.33 − 1.00 − 1.53 − 0 = 30.80
    }

    @Test
    void 聚合列全空时按零成交处理不抛异常() {
        PromoItemVo vo = row(null, null, null, null, null, null, null);
        PromoReportService.applyProfit(vo);
        assertMoney("0.00", vo.getNetProfit());
        assertMoney("0.00", vo.getFreightCost());
        assertNull(vo.getProfitGaps());
        assertNull(vo.getNetRoi());
    }
}
