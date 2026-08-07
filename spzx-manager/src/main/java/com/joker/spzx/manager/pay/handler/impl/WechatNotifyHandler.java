package com.joker.spzx.manager.pay.handler.impl;

import com.joker.spzx.manager.pay.config.WxPayConfig;
import com.joker.spzx.manager.pay.handler.ChannelNotifyHandler;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import com.github.binarywang.wxpay.service.WxPayService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class WechatNotifyHandler implements ChannelNotifyHandler {

    @Autowired
    private WxPayService wxPayService;

    @Override
    public String getChannel() { return "wechat"; }

    @Override
    public PayNotifyResult parseAndVerify(String body, HttpServletRequest request) {
        PayNotifyResult result = new PayNotifyResult();
        try {
            var notifyResult = wxPayService.parseOrderNotifyV3Result(body, null);
            var resultData = notifyResult.getResult();
            result.setSuccess(true);
            result.setOrderNo(resultData.getOutTradeNo());
            result.setOutTradeNo(resultData.getTransactionId());
            result.setAmount(new java.math.BigDecimal(resultData.getAmount().getTotal()).divide(new java.math.BigDecimal("100")));
            result.setPayType(1);
            result.setRawBody(body);
        } catch (Exception e) {
            log.error("微信支付回调解析失败", e);
            result.setSuccess(false);
            result.setRawBody(body);
        }
        return result;
    }

    @Override
    public RefundNotifyResult parseAndVerifyRefund(String body, HttpServletRequest request) {
        RefundNotifyResult result = new RefundNotifyResult();
        try {
            var refundResult = wxPayService.parseRefundNotifyV3Result(body, null);
            var resultData = refundResult.getResult();
            result.setSuccess(true);
            result.setOrderNo(resultData.getOutTradeNo());
            result.setRefundNo(resultData.getOutRefundNo());
            result.setRefundAmount(new java.math.BigDecimal(resultData.getAmount().getRefund()).divide(new java.math.BigDecimal("100")));
            result.setPayType(1);
            result.setRawBody(body);
        } catch (Exception e) {
            log.error("微信退款回调解析失败", e);
            result.setSuccess(false);
            result.setRawBody(body);
        }
        return result;
    }

    @Override
    public String successResponse() {
        return "<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>";
    }

    @Override
    public String failResponse() {
        return "<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[ERROR]]></return_msg></xml>";
    }
}
