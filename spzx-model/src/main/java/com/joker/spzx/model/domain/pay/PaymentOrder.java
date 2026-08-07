package com.joker.spzx.model.domain.pay;

import com.joker.spzx.model.enums.pay.PaymentStatusEnum;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class PaymentOrder {

    private Long id;
    private String orderNo;
    private String outTradeNo;
    private String tradeNo;
    private Long merchantId;
    private String merchantName;
    private Integer payType;
    private String channel;
    private BigDecimal amount;
    private BigDecimal fee;
    private String subject;
    private String body;
    private String attach;
    private Integer status;
    private String clientIp;
    private String notifyUrl;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private LocalDateTime expireTime;
    private LocalDateTime callbackTime;
    private String callbackContent;
    private Integer callbackCount;
    private LocalDateTime nextNotifyTime;
    private Integer platformType;

    private BigDecimal refundedAmount = BigDecimal.ZERO;

    public PaymentStatusEnum getStatusEnum() {
        return PaymentStatusEnum.fromCode(status);
    }

    public void markPaying() {
        checkTransition(PaymentStatusEnum.PAYING);
        this.status = PaymentStatusEnum.PAYING.getCode();
    }

    public void markPaid(String outTradeNo, String callbackContent) {
        if (this.status != null && this.status == PaymentStatusEnum.PAID.getCode()) {
            return;
        }
        checkTransition(PaymentStatusEnum.PAID);
        this.status = PaymentStatusEnum.PAID.getCode();
        this.outTradeNo = outTradeNo;
        this.callbackContent = callbackContent;
        this.callbackTime = LocalDateTime.now();
    }

    public void markClosed() {
        checkTransition(PaymentStatusEnum.CLOSED);
        this.status = PaymentStatusEnum.CLOSED.getCode();
    }

    public void markPayError() {
        checkTransition(PaymentStatusEnum.PAY_ERROR);
        this.status = PaymentStatusEnum.PAY_ERROR.getCode();
    }

    public void markRefunding() {
        checkTransition(PaymentStatusEnum.REFUNDING);
        this.status = PaymentStatusEnum.REFUNDING.getCode();
    }

    public void markRefunded() {
        this.status = PaymentStatusEnum.REFUNDED.getCode();
    }

    public void markPartialRefunded() {
        this.status = PaymentStatusEnum.PARTIAL_REFUNDED.getCode();
    }

    public void validateRefund(BigDecimal refundAmount) {
        if (status != PaymentStatusEnum.PAID.getCode()
                && status != PaymentStatusEnum.PARTIAL_REFUNDED.getCode()) {
            throw new PayException(PayErrorCode.REFUND_ORDER_NOT_PAID);
        }
        BigDecimal refundable = amount.subtract(refundedAmount);
        if (refundAmount.compareTo(refundable) > 0) {
            throw new PayException(PayErrorCode.REFUND_EXCEED);
        }
    }

    public void applyRefund(BigDecimal refundAmount) {
        validateRefund(refundAmount);
        this.refundedAmount = this.refundedAmount.add(refundAmount);
        if (this.refundedAmount.compareTo(this.amount) == 0) {
            markRefunded();
        } else {
            markPartialRefunded();
        }
    }

    private void checkTransition(PaymentStatusEnum to) {
        PaymentStatusEnum from = status != null ? PaymentStatusEnum.fromCode(status) : PaymentStatusEnum.UNPAID;
        switch (from) {
            case UNPAID -> {
                if (to != PaymentStatusEnum.PAYING && to != PaymentStatusEnum.CLOSED) throw invalidTransition(from, to);
            }
            case PAYING -> {
                if (to != PaymentStatusEnum.PAID && to != PaymentStatusEnum.PAY_ERROR && to != PaymentStatusEnum.CLOSED) throw invalidTransition(from, to);
            }
            case PAID -> {
                if (to != PaymentStatusEnum.REFUNDING && to != PaymentStatusEnum.PARTIAL_REFUNDED && to != PaymentStatusEnum.PAID) throw invalidTransition(from, to);
            }
            case PARTIAL_REFUNDED -> {
                if (to != PaymentStatusEnum.REFUNDING && to != PaymentStatusEnum.REFUNDED && to != PaymentStatusEnum.PARTIAL_REFUNDED) throw invalidTransition(from, to);
            }
            case REFUNDING -> {
                if (to != PaymentStatusEnum.PAID && to != PaymentStatusEnum.PARTIAL_REFUNDED
                        && to != PaymentStatusEnum.REFUNDED && to != PaymentStatusEnum.REFUND_FAILED) throw invalidTransition(from, to);
            }
            case REFUND_FAILED -> {
                if (to != PaymentStatusEnum.REFUNDING) throw invalidTransition(from, to);
            }
            case PAY_ERROR -> {
                if (to != PaymentStatusEnum.PAYING) throw invalidTransition(from, to);
            }
            case REFUNDED, CLOSED -> throw invalidTransition(from, to);
        }
    }

    private PayException invalidTransition(PaymentStatusEnum from, PaymentStatusEnum to) {
        return new PayException(PayErrorCode.ORDER_STATUS_INVALID, from.getDesc() + " → " + to.getDesc());
    }
}
