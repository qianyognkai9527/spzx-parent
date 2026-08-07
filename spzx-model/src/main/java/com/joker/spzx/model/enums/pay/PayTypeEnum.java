package com.joker.spzx.model.enums.pay;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum PayTypeEnum {
    WECHAT_JSAPI(1, "wechat_jsapi", "微信JSAPI支付"),
    WECHAT_NATIVE(2, "wechat_native", "微信扫码支付"),
    WECHAT_APP(3, "wechat_app", "微信APP支付"),
    WECHAT_H5(4, "wechat_h5", "微信H5支付"),
    WECHAT_MINI(5, "wechat_mini", "微信小程序支付"),
    ALIPAY_PAGE(6, "alipay_page", "支付宝电脑网站支付"),
    ALIPAY_WAP(7, "alipay_wap", "支付宝手机网站支付"),
    ALIPAY_APP(8, "alipay_app", "支付宝APP支付"),
    ALIPAY_SCAN(9, "alipay_scan", "支付宝扫码支付"),
    ALIPAY_MINI(10, "alipay_mini", "支付宝小程序支付"),
    UNIONPAY_JSAPI(11, "unionpay_jsapi", "银联云闪付JSAPI"),
    UNIONPAY_B2B(12, "unionpay_b2b", "银联企业网银"),
    UNIONPAY_QR(13, "unionpay_qr", "银联二维码"),
    PAYPAL_CARD(14, "paypal_card", "PayPal信用卡"),
    PAYPAL_ORDER(15, "paypal_order", "PayPal Orders"),
    STRIPE_CARD(16, "stripe_card", "Stripe信用卡"),
    STRIPE_LINK(17, "stripe_link", "Stripe Link"),
    DOUYIN_MINI(18, "douyin_mini", "抖音小程序支付"),
    DOUYIN_GUARANTEE(19, "douyin_guarantee", "抖音担保交易"),
    JD_QUICK(20, "jd_quick", "京东快捷支付"),
    JD_BAITIAO(21, "jd_baitiao", "京东白条"),
    LAKALA_POS(22, "lakala_pos", "拉卡拉POS"),
    LAKALA_QR(23, "lakala_qr", "拉卡拉扫码"),
    AGGREGATE_QR(24, "aggregate_qr", "聚合扫码"),
    AGGREGATE_H5(25, "aggregate_h5", "聚合H5");

    private final int code;
    private final String channel;
    private final String desc;

    public static PayTypeEnum fromCode(int code) {
        for (PayTypeEnum e : values()) {
            if (e.code == code) return e;
        }
        throw new IllegalArgumentException("Unknown PayType code: " + code);
    }

    public static PayTypeEnum fromChannel(String channel) {
        for (PayTypeEnum e : values()) {
            if (e.channel.equals(channel)) return e;
        }
        throw new IllegalArgumentException("Unknown PayType channel: " + channel);
    }

    public boolean isWechat() {
        return this.channel.startsWith("wechat");
    }

    public boolean isAlipay() {
        return this.channel.startsWith("alipay");
    }

    public boolean isUnionpay() {
        return this.channel.startsWith("unionpay");
    }

    public boolean isPaypal() {
        return this.channel.startsWith("paypal");
    }

    public boolean isStripe() {
        return this.channel.startsWith("stripe");
    }

    public boolean isDouyin() {
        return this.channel.startsWith("douyin");
    }

    public boolean isJd() {
        return this.channel.startsWith("jd");
    }

    public boolean isLakala() {
        return this.channel.startsWith("lakala");
    }

    public boolean isAggregate() {
        return this.channel.startsWith("aggregate");
    }
}
