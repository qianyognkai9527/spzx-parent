package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.facade.PaymentFacade;
import com.joker.spzx.manager.pay.handler.ChannelNotifyHandler;
import com.joker.spzx.manager.pay.handler.NotifyHandlerFactory;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.IOException;

@Slf4j
@Tag(name = "支付回调V2", description = "统一回调入口")
@RestController
@RequestMapping("/api/v2/pay/notify")
public class NotifyController {

    @Autowired
    private NotifyHandlerFactory handlerFactory;
    @Autowired
    private PaymentFacade paymentFacade;

    @Operation(summary = "支付回调")
    @PostMapping("/{channel}")
    public String notify(@PathVariable String channel, HttpServletRequest request) {
        ChannelNotifyHandler handler = handlerFactory.getHandler(channel);
        String body = readBody(request);
        PayNotifyResult result = handler.parseAndVerify(body, request);

        if (result.getOrderNo() != null) {
            PayTypeEnum payType = paymentFacade.resolvePayType(result.getOrderNo());
            if (payType != null) {
                result.setPayType(payType.getCode());
            }
        }

        paymentFacade.handleNotify(result, channel);
        return result.isSuccess() ? handler.successResponse() : handler.failResponse();
    }

    @Operation(summary = "退款回调")
    @PostMapping("/{channel}/refund")
    public String refundNotify(@PathVariable String channel, HttpServletRequest request) {
        ChannelNotifyHandler handler = handlerFactory.getHandler(channel);
        String body = readBody(request);
        RefundNotifyResult result = handler.parseAndVerifyRefund(body, request);

        paymentFacade.handleRefundNotify(result, channel);
        return result.isSuccess() ? handler.successResponse() : handler.failResponse();
    }

    private String readBody(HttpServletRequest request) {
        try (BufferedReader reader = request.getReader()) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
            return sb.toString();
        } catch (IOException e) {
            log.error("读取回调body失败", e);
            return "";
        }
    }
}
