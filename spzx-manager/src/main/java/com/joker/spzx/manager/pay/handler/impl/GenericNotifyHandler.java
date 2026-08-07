package com.joker.spzx.manager.pay.handler.impl;

import com.joker.spzx.manager.pay.handler.ChannelNotifyHandler;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class GenericNotifyHandler implements ChannelNotifyHandler {

    @Override
    public String getChannel() { return "generic"; }

    @Override
    public PayNotifyResult parseAndVerify(String body, HttpServletRequest request) {
        PayNotifyResult result = new PayNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    @Override
    public RefundNotifyResult parseAndVerifyRefund(String body, HttpServletRequest request) {
        RefundNotifyResult result = new RefundNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    @Override
    public String successResponse() { return "SUCCESS"; }

    @Override
    public String failResponse() { return "FAIL"; }
}
