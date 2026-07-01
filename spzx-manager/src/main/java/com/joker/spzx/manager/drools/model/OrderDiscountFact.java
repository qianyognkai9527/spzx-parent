package com.joker.spzx.manager.drools.model;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 订单折扣规则事实对象（示例）
 */
@Data
public class OrderDiscountFact implements Serializable {

    private static final BigDecimal VIP_THRESHOLD = new BigDecimal("100");
    private static final BigDecimal NORMAL_THRESHOLD = new BigDecimal("200");
    private static final BigDecimal VIP_RATE = new BigDecimal("0.8");
    private static final BigDecimal NORMAL_RATE = new BigDecimal("0.95");

    private BigDecimal orderAmount;

    /**
     * 会员等级：VIP / NORMAL
     */
    private String memberLevel;

    /**
     * 规则引擎计算后的应付金额（折后）
     */
    private BigDecimal payableAmount;

    /**
     * VIP会员且订单金额>=100，满足VIP折扣条件
     */
    private boolean vipDiscountEligible;

    /**
     * 普通会员且订单金额>=200，满足普通折扣条件
     */
    private boolean normalDiscountEligible;

    /**
     * 在规则执行前调用，预计算标志位，
     * 避免在DRL中使用 == null / == "VIP" 等不兼容表达式。
     * 同时设置默认原价，折扣规则会覆盖此值。
     */
    public void preprocess() {
        this.vipDiscountEligible = "VIP".equals(this.memberLevel)
                && this.orderAmount != null
                && this.orderAmount.compareTo(VIP_THRESHOLD) >= 0;
        this.normalDiscountEligible = "NORMAL".equals(this.memberLevel)
                && this.orderAmount != null
                && this.orderAmount.compareTo(NORMAL_THRESHOLD) >= 0;
        if (this.payableAmount == null && this.orderAmount != null) {
            this.payableAmount = this.orderAmount;
        }
    }

    public void applyVipDiscount() {
        this.payableAmount = orderAmount.multiply(VIP_RATE);
    }

    public void applyNormalDiscount() {
        this.payableAmount = orderAmount.multiply(NORMAL_RATE);
    }
}
