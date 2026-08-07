package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.pay.strategy.PayStrategy;
import com.joker.spzx.manager.pay.strategy.PayStrategyFactory;
import com.joker.spzx.manager.pay.strategy.impl.AbstractAlipayPayStrategy;
import com.joker.spzx.manager.service.PaymentService;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@RestController
@Tag(name = "支付接口", description = "统一支付网关")
@RequestMapping("/api/pay")
public class PaymentController {

    @Autowired
    private PaymentService paymentService;
    @Autowired
    private PayStrategyFactory strategyFactory;

    @Operation(summary = "创建支付订单")
    @PostMapping("/create")
    public Result<PayCreateVO> createPayment(@RequestBody @Validated PayCreateDTO dto) {
        PayCreateVO vo = paymentService.createPayment(dto);
        return Result.build(vo);
    }

    @Operation(summary = "微信支付回调")
    @PostMapping("/notify/wechat")
    public String wechatNotify(HttpServletRequest request) {
        String body = readBody(request);
        PayNotifyResult result = paymentService.handleWechatNotify(body);
        if (result.isSuccess()) {
            return "<xml><return_code><![CDATA[SUCCESS]]></return_code><return_msg><![CDATA[OK]]></return_msg></xml>";
        }
        return "<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[ERROR]]></return_msg></xml>";
    }

    @Operation(summary = "支付宝支付回调")
    @PostMapping("/notify/alipay")
    public String alipayNotify(HttpServletRequest request) {
        Map<String, String> params = parseAlipayParams(request);
        PayNotifyResult result = paymentService.handleAlipayNotify(params);
        return result.isSuccess() ? "success" : "fail";
    }

    @Operation(summary = "微信退款回调")
    @PostMapping("/notify/wechat/refund")
    public String wechatRefundNotify(HttpServletRequest request) {
        String body = readBody(request);
        var result = paymentService.handleWechatRefundNotify(body);
        return result.isSuccess() ? "SUCCESS" : "FAIL";
    }

    @Operation(summary = "支付宝退款回调")
    @PostMapping("/notify/alipay/refund")
    public String alipayRefundNotify(HttpServletRequest request) {
        Map<String, String> params = parseAlipayParams(request);
        var result = paymentService.handleAlipayRefundNotify(params);
        return result.isSuccess() ? "success" : "fail";
    }

    @Operation(summary = "查询支付状态")
    @GetMapping("/query/{orderNo}")
    public Result<PayQueryVO> queryPayment(@PathVariable String orderNo,
                                          @RequestParam Integer payType) {
        PayQueryVO vo = paymentService.queryPayment(orderNo, payType);
        return Result.build(vo);
    }

    @Operation(summary = "关闭支付订单")
    @PostMapping("/close/{orderNo}")
    public Result<Void> closePayment(@PathVariable String orderNo,
                                     @RequestParam Integer payType) {
        paymentService.closePayment(orderNo, payType);
        return Result.build(null);
    }

    @Operation(summary = "申请退款")
    @PostMapping("/refund")
    public Result<Void> refund(@RequestBody @Validated RefundCreateDTO dto) {
        paymentService.refund(dto);
        return Result.build(null);
    }

    @Operation(summary = "获取所有支付方式")
    @GetMapping("/methods")
    public Result<PayTypeEnum[]> getPayMethods() {
        return Result.build(PayTypeEnum.values());
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

    private Map<String, String> parseAlipayParams(HttpServletRequest request) {
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
