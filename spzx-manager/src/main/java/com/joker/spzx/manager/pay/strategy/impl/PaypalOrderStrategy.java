package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.joker.spzx.manager.pay.config.PaypalConfig;
import com.joker.spzx.manager.pay.strategy.AbstractPayStrategy;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import com.paypal.core.PayPalHttpClient;
import com.paypal.orders.AmountWithBreakdown;
import com.paypal.orders.Order;
import com.paypal.orders.OrderRequest;
import com.paypal.orders.OrdersCreateRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class PaypalOrderStrategy extends AbstractPayStrategy {

    @Autowired
    private PayPalHttpClient payPalHttpClient;
    @Autowired
    private PaypalConfig paypalConfig;

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.PAYPAL_ORDER; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            OrderRequest orderRequest = new OrderRequest();
            orderRequest.checkoutPaymentIntent("CAPTURE");
            AmountWithBreakdown amount = new AmountWithBreakdown()
                    .currencyCode("CNY").value(dto.getAmount().toPlainString());
            com.paypal.orders.PurchaseUnitRequest purchaseUnit = new com.paypal.orders.PurchaseUnitRequest()
                    .referenceId(dto.getOrderNo()).description(dto.getSubject()).amountWithBreakdown(amount);
            orderRequest.purchaseUnits(java.util.List.of(purchaseUnit));
            OrdersCreateRequest request = new OrdersCreateRequest();
            request.requestBody(orderRequest);
            Order order = payPalHttpClient.execute(request).result();
            PayCreateVO vo = new PayCreateVO();
            vo.setPrepayId(order.id());
            String approveUrl = order.links().stream()
                    .filter(l -> "approve".equals(l.rel())).findFirst()
                    .map(com.paypal.orders.LinkDescription::href).orElse("");
            vo.setPayUrl(approveUrl);
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("PayPal创建订单失败: " + e.getMessage(), e);
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
        log.info("[PayPal] 查询订单 orderNo={}", orderNo);
        return new PayQueryVO();
    }

    @Override
    public void closePayment(String orderNo) {
        log.info("[PayPal] 关闭订单 orderNo={}", orderNo);
    }

    @Override
    public void refund(RefundCreateDTO dto) {
        log.info("[PayPal] 退款 orderNo={}", dto.getOrderNo());
    }
}
