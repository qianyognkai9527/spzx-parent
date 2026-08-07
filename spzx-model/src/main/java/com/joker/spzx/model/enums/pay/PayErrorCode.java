package com.joker.spzx.model.enums.pay;

import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum PayErrorCode {

    SUCCESS              ("PAY-0000", "成功", 200),
    SYSTEM_ERROR         ("PAY-0001", "系统异常", 500),
    PARAM_INVALID        ("PAY-0002", "参数校验失败", 400),

    ORDER_EXISTS         ("PAY-1001", "订单已存在，请勿重复下单", 409),
    ORDER_PROCESSING     ("PAY-1002", "订单正在处理中", 409),
    ORDER_STATUS_INVALID ("PAY-1003", "订单状态不允许此操作", 409),
    AMOUNT_INVALID       ("PAY-1004", "支付金额必须大于0", 400),
    MERCHANT_NOT_FOUND   ("PAY-1005", "商户不存在或已禁用", 404),
    CHANNEL_UNAVAILABLE  ("PAY-1006", "支付渠道暂不可用", 503),
    NO_AVAILABLE_CHANNEL ("PAY-1007", "无可用支付渠道", 503),
    ORDER_NOT_FOUND      ("PAY-1008", "订单不存在", 404),

    NOTIFY_SIGN_FAIL     ("PAY-2001", "回调验签失败", 403),
    NOTIFY_ORDER_NOT_FOUND("PAY-2002", "回调订单不存在", 404),
    NOTIFY_DUPLICATE     ("PAY-2003", "重复回调，幂等处理", 200),
    NOTIFY_PARSE_FAIL    ("PAY-2004", "回调数据解析失败", 400),

    REFUND_EXCEED        ("PAY-3001", "退款金额超过可退金额", 400),
    REFUND_ORDER_NOT_PAID("PAY-3002", "原订单未支付，不可退款", 409),
    REFUND_DUPLICATE     ("PAY-3003", "退款单已存在", 409),
    REFUND_RETRY_EXCEED  ("PAY-3004", "退款重试次数超限，需人工处理", 500),

    RISK_REJECT          ("PAY-4001", "风控拦截", 403),
    RISK_REVIEW          ("PAY-4002", "风控审核中", 202),
    MERCHANT_LIMIT_EXCEED("PAY-4003", "商户交易限额超出", 403),

    CHANNEL_CALL_FAIL    ("PAY-5001", "渠道调用失败", 502),
    CHANNEL_TIMEOUT      ("PAY-5002", "渠道调用超时", 504),
    CHANNEL_CIRCUIT_OPEN ("PAY-5003", "渠道熔断中，请稍后重试", 503),

    RECONCILE_DIFF_FOUND ("PAY-6001", "对账差异已记录", 200),
    RECONCILE_BATCH_FAIL ("PAY-6002", "对账批次执行失败", 500);

    private final String code;
    private final String message;
    private final int httpStatus;
}
