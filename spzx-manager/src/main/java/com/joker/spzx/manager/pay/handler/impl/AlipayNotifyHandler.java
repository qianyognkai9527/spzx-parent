package com.joker.spzx.manager.pay.handler.impl;

import com.alipay.api.internal.util.AlipaySignature;
import com.joker.spzx.manager.pay.config.AlipayConfig;
import com.joker.spzx.manager.pay.handler.ChannelNotifyHandler;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Component
public class AlipayNotifyHandler implements ChannelNotifyHandler {

    @Autowired
    private AlipayConfig alipayConfig;

    @Override
    public String getChannel() { return "alipay"; }

    @Override
    public PayNotifyResult parseAndVerify(String body, HttpServletRequest request) {
        Map<String, String> params = parseParams(request);
        PayNotifyResult result = new PayNotifyResult();
        try {
            boolean signVerified = AlipaySignature.rsaCheckV1(
                params, alipayConfig.getAlipayPublicKey(), alipayConfig.getCharset(), alipayConfig.getSignType());
            result.setSuccess(signVerified && "TRADE_SUCCESS".equals(params.get("trade_status")));
            result.setOrderNo(params.get("out_trade_no"));
            result.setOutTradeNo(params.get("trade_no"));
            result.setAmount(new BigDecimal(params.getOrDefault("total_amount", "0")));
            result.setRawBody(params.toString());
        } catch (Exception e) {
            log.error("支付宝回调验签失败", e);
            result.setSuccess(false);
            result.setRawBody(params.toString());
        }
        return result;
    }

    @Override
    public RefundNotifyResult parseAndVerifyRefund(String body, HttpServletRequest request) {
        Map<String, String> params = parseParams(request);
        RefundNotifyResult result = new RefundNotifyResult();
        result.setSuccess("REFUND_SUCCESS".equals(params.get("refund_status")));
        result.setOrderNo(params.get("out_trade_no"));
        result.setRefundNo(params.get("out_biz_no"));
        result.setRefundAmount(new BigDecimal(params.getOrDefault("refund_amount", "0")));
        result.setRawBody(params.toString());
        return result;
    }

    @Override
    public String successResponse() { return "success"; }

    @Override
    public String failResponse() { return "fail"; }

    private Map<String, String> parseParams(HttpServletRequest request) {
        Map<String, String> params = new HashMap<>();
        Map<String, String[]> requestParams = request.getParameterMap();
        for (String name : requestParams.keySet()) {
            String[] values = requestParams.get(name);
            StringBuilder valueStr = new StringBuilder();
            for (int i = 0; i < values.length; i++) {
                valueStr.append(i == values.length - 1 ? values[i] : values[i] + ",");
            }
            params.put(name, valueStr.toString());
        }
        return params;
    }
}
