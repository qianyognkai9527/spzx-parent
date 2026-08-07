package com.joker.spzx.manager.pay.strategy;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import lombok.extern.slf4j.Slf4j;

@Slf4j
public abstract class AbstractPayStrategy implements PayStrategy {

    @Override
    public final PayCreateVO createPayment(PayCreateDTO dto) {
        validate(dto);
        PayCreateVO vo = doCreatePayment(dto);
        log.info("[{}] 创建支付订单 orderNo={}, amount={}", getPayType().getChannel(), dto.getOrderNo(), dto.getAmount());
        return vo;
    }

    @Override
    public final PayNotifyResult handleNotify(String body) {
        PayNotifyResult result = doHandleNotify(body);
        if (result.isSuccess()) {
            log.info("[{}] 支付成功 orderNo={}, outTradeNo={}", getPayType().getChannel(), result.getOrderNo(), result.getOutTradeNo());
        } else {
            log.warn("[{}] 支付失败 body={}", getPayType().getChannel(), body);
        }
        return result;
    }

    @Override
    public final RefundNotifyResult handleRefundNotify(String body) {
        RefundNotifyResult result = doHandleRefundNotify(body);
        log.info("[{}] 退款通知 orderNo={}, success={}", getPayType().getChannel(), result.getOrderNo(), result.isSuccess());
        return result;
    }

    protected void validate(PayCreateDTO dto) {
        if (dto.getAmount() == null || dto.getAmount().signum() <= 0) {
            throw new IllegalArgumentException("支付金额必须大于0");
        }
    }

    protected abstract PayCreateVO doCreatePayment(PayCreateDTO dto);
    protected abstract PayNotifyResult doHandleNotify(String body);
    protected abstract RefundNotifyResult doHandleRefundNotify(String body);
}
