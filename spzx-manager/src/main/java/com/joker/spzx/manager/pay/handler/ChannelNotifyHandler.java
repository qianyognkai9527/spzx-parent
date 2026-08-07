package com.joker.spzx.manager.pay.handler;

import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import jakarta.servlet.http.HttpServletRequest;

import java.util.Map;

public interface ChannelNotifyHandler {

    String getChannel();

    PayNotifyResult parseAndVerify(String body, HttpServletRequest request);

    RefundNotifyResult parseAndVerifyRefund(String body, HttpServletRequest request);

    String successResponse();

    String failResponse();
}
