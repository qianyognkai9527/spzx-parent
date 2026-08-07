package com.joker.spzx.model.enums.pay;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum ChannelEnum {
    WECHAT("wechat", "微信支付"),
    ALIPAY("alipay", "支付宝"),
    UNIONPAY("unionpay", "银联"),
    PAYPAL("paypal", "PayPal"),
    STRIPE("stripe", "Stripe"),
    DOUYIN("douyin", "抖音"),
    JD("jd", "京东"),
    LAKALA("lakala", "拉卡拉"),
    AGGREGATE("aggregate", "聚合");

    private final String code;
    private final String desc;

    public static ChannelEnum fromCode(String code) {
        for (ChannelEnum e : values()) {
            if (e.code.equals(code)) return e;
        }
        throw new IllegalArgumentException("Unknown channel: " + code);
    }

    public static ChannelEnum fromPayType(PayTypeEnum payType) {
        if (payType.isWechat()) return WECHAT;
        if (payType.isAlipay()) return ALIPAY;
        if (payType.isUnionpay()) return UNIONPAY;
        if (payType.isPaypal()) return PAYPAL;
        if (payType.isStripe()) return STRIPE;
        if (payType.isDouyin()) return DOUYIN;
        if (payType.isJd()) return JD;
        if (payType.isLakala()) return LAKALA;
        if (payType.isAggregate()) return AGGREGATE;
        throw new IllegalArgumentException("Unknown channel for payType: " + payType);
    }
}
