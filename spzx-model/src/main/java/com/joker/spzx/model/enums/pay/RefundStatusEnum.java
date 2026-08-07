package com.joker.spzx.model.enums.pay;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum RefundStatusEnum {
    REFUND_PENDING(0, "退款待处理"),
    REFUND_PROCESSING(1, "退款处理中"),
    REFUND_SUCCESS(2, "退款成功"),
    REFUND_FAILED(3, "退款失败");

    private final int code;
    private final String desc;

    public static RefundStatusEnum fromCode(int code) {
        for (RefundStatusEnum e : values()) {
            if (e.code == code) return e;
        }
        throw new IllegalArgumentException("Unknown RefundStatus code: " + code);
    }
}
