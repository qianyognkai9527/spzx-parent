package com.joker.spzx.model.enums.pay;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum PaymentStatusEnum {
    UNPAID(0, "未支付"),
    PAYING(1, "支付中"),
    PAID(2, "已支付"),
    CLOSED(3, "已关闭"),
    REFUNDING(4, "退款中"),
    PARTIAL_REFUNDED(5, "部分退款"),
    REFUNDED(6, "已退款"),
    REFUND_FAILED(7, "退款失败"),
    PAY_ERROR(8, "支付失败");

    private final int code;
    private final String desc;

    public static PaymentStatusEnum fromCode(int code) {
        for (PaymentStatusEnum e : values()) {
            if (e.code == code) return e;
        }
        throw new IllegalArgumentException("Unknown PaymentStatus code: " + code);
    }
}
