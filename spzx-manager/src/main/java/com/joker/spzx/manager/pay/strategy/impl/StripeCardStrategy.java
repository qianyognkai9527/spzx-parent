package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.PaymentInfoMapper;
import com.joker.spzx.manager.pay.config.StripeConfig;
import com.joker.spzx.manager.pay.strategy.AbstractPayStrategy;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.entity.pay.PaymentInfo;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import com.stripe.Stripe;
import com.stripe.model.PaymentIntent;
import com.stripe.model.Refund;
import com.stripe.param.PaymentIntentCreateParams;
import com.stripe.param.RefundCreateParams;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class StripeCardStrategy extends AbstractPayStrategy {

    @Autowired
    private StripeConfig stripeConfig;
    @Autowired
    private PaymentInfoMapper paymentInfoMapper;

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.STRIPE_CARD; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            Stripe.apiKey = stripeConfig.getApiKey();
            PaymentIntentCreateParams params = PaymentIntentCreateParams.builder()
                    .setAmount(dto.getAmount().multiply(new BigDecimal("100")).longValue())
                    .setCurrency("cny")
                    .setDescription(dto.getSubject())
                    .putAllMetadata(java.util.Map.of("orderNo", dto.getOrderNo()))
                    .setAutomaticPaymentMethods(PaymentIntentCreateParams.AutomaticPaymentMethods.builder()
                            .setEnabled(true).build())
                    .build();
            PaymentIntent intent = PaymentIntent.create(params);
            PayCreateVO vo = new PayCreateVO();
            vo.setPrepayId(intent.getId());
            vo.setPayUrl(intent.getClientSecret());
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("Stripe创建支付失败: " + e.getMessage(), e);
        }
    }

    @Override
    protected PayNotifyResult doHandleNotify(String body) {
        PayNotifyResult result = new PayNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    @Override
    protected RefundNotifyResult doHandleRefundNotify(String body) {
        RefundNotifyResult result = new RefundNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    @Override
    public PayQueryVO queryPayment(String orderNo) {
        try {
            Stripe.apiKey = stripeConfig.getApiKey();
            String intentId = resolveIntentId(orderNo);
            PaymentIntent intent = PaymentIntent.retrieve(intentId);
            PayQueryVO vo = new PayQueryVO();
            vo.setOrderNo(orderNo);
            vo.setOutTradeNo(intent.getId());
            vo.setTradeStatus(intent.getStatus());
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("Stripe查询失败: " + e.getMessage(), e);
        }
    }

    @Override
    public void closePayment(String orderNo) {
        try {
            Stripe.apiKey = stripeConfig.getApiKey();
            String intentId = resolveIntentId(orderNo);
            PaymentIntent intent = PaymentIntent.retrieve(intentId);
            intent.cancel();
        } catch (Exception e) {
            throw new RuntimeException("Stripe关闭订单失败", e);
        }
    }

    @Override
    public void refund(RefundCreateDTO dto) {
        try {
            Stripe.apiKey = stripeConfig.getApiKey();
            String intentId = resolveIntentId(dto.getOrderNo());
            RefundCreateParams params = RefundCreateParams.builder()
                    .setPaymentIntent(intentId)
                    .setAmount(dto.getRefundAmount().multiply(new BigDecimal("100")).longValue())
                    .build();
            Refund.create(params);
        } catch (Exception e) {
            throw new RuntimeException("Stripe退款失败", e);
        }
    }

    private String resolveIntentId(String orderNo) {
        PaymentInfo info = paymentInfoMapper.selectOne(
            new LambdaQueryWrapper<PaymentInfo>()
                .eq(PaymentInfo::getOrderNo, orderNo));
        if (info == null || info.getOutTradeNo() == null) {
            throw new RuntimeException("Stripe订单不存在或未创建PaymentIntent: " + orderNo);
        }
        return info.getOutTradeNo();
    }
}
