package com.joker.spzx.model.exception;

import com.joker.spzx.model.enums.pay.PayErrorCode;
import lombok.Getter;

@Getter
public class PayException extends RuntimeException {

    private final String errorCode;
    private final int httpStatus;

    public PayException(PayErrorCode payErrorCode) {
        super(payErrorCode.getMessage());
        this.errorCode = payErrorCode.getCode();
        this.httpStatus = payErrorCode.getHttpStatus();
    }

    public PayException(PayErrorCode payErrorCode, String detail) {
        super(payErrorCode.getMessage() + ": " + detail);
        this.errorCode = payErrorCode.getCode();
        this.httpStatus = payErrorCode.getHttpStatus();
    }

    public PayException(PayErrorCode payErrorCode, Throwable cause) {
        super(payErrorCode.getMessage(), cause);
        this.errorCode = payErrorCode.getCode();
        this.httpStatus = payErrorCode.getHttpStatus();
    }
}
