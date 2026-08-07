package com.joker.spzx.model.domain.pay;

import com.joker.spzx.model.enums.pay.RefundStatusEnum;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class RefundOrder {

    private Long id;
    private String refundNo;
    private String orderNo;
    private String outRefundNo;
    private Long merchantId;
    private String channel;
    private BigDecimal refundAmount;
    private BigDecimal totalAmount;
    private String reason;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private LocalDateTime callbackTime;
    private String callbackContent;
    private Integer retryCount;

    public RefundStatusEnum getStatusEnum() {
        return RefundStatusEnum.fromCode(status);
    }

    public void markProcessing() {
        checkTransition(RefundStatusEnum.REFUND_PROCESSING);
        this.status = RefundStatusEnum.REFUND_PROCESSING.getCode();
    }

    public void markSuccess(String outRefundNo, String callbackContent) {
        if (this.status != null && this.status == RefundStatusEnum.REFUND_SUCCESS.getCode()) {
            return;
        }
        checkTransition(RefundStatusEnum.REFUND_SUCCESS);
        this.status = RefundStatusEnum.REFUND_SUCCESS.getCode();
        this.outRefundNo = outRefundNo;
        this.callbackContent = callbackContent;
        this.callbackTime = LocalDateTime.now();
    }

    public void markFailed() {
        checkTransition(RefundStatusEnum.REFUND_FAILED);
        this.status = RefundStatusEnum.REFUND_FAILED.getCode();
    }

    public void markPending() {
        checkTransition(RefundStatusEnum.REFUND_PENDING);
        this.status = RefundStatusEnum.REFUND_PENDING.getCode();
    }

    public void incrementRetry() {
        this.retryCount = (this.retryCount == null ? 0 : this.retryCount) + 1;
    }

    private void checkTransition(RefundStatusEnum to) {
        RefundStatusEnum from = status != null ? RefundStatusEnum.fromCode(status) : RefundStatusEnum.REFUND_PENDING;
        switch (from) {
            case REFUND_PENDING -> {
                if (to != RefundStatusEnum.REFUND_PROCESSING && to != RefundStatusEnum.REFUND_FAILED) throw invalidTransition(from, to);
            }
            case REFUND_PROCESSING -> {
                if (to != RefundStatusEnum.REFUND_SUCCESS && to != RefundStatusEnum.REFUND_FAILED) throw invalidTransition(from, to);
            }
            case REFUND_FAILED -> {
                if (to != RefundStatusEnum.REFUND_PENDING) throw invalidTransition(from, to);
            }
            case REFUND_SUCCESS -> throw invalidTransition(from, to);
        }
    }

    private PayException invalidTransition(RefundStatusEnum from, RefundStatusEnum to) {
        return new PayException(PayErrorCode.ORDER_STATUS_INVALID, from.getDesc() + " → " + to.getDesc());
    }
}
