package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.facade.PaymentFacade;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

@Tag(name = "支付接口V2", description = "统一支付网关 v2")
@RestController
@RequestMapping("/api/v2/pay")
public class PayV2Controller {

    @Autowired
    private PaymentFacade paymentFacade;

    @Operation(summary = "创建支付订单")
    @PostMapping("/create")
    public Result<PayCreateVO> createPayment(@RequestBody @Validated PayCreateDTO dto) {
        return Result.build(paymentFacade.createPayment(dto));
    }

    @Operation(summary = "查询支付状态")
    @GetMapping("/query/{orderNo}")
    public Result<PayQueryVO> queryPayment(@PathVariable String orderNo,
                                           @RequestParam Integer payType) {
        return Result.build(paymentFacade.queryPayment(orderNo, payType));
    }

    @Operation(summary = "关闭支付订单")
    @PostMapping("/close/{orderNo}")
    public Result<Void> closePayment(@PathVariable String orderNo,
                                     @RequestParam Integer payType) {
        paymentFacade.closePayment(orderNo, payType);
        return Result.build(null);
    }

    @Operation(summary = "申请退款")
    @PostMapping("/refund")
    public Result<Void> refund(@RequestBody @Validated RefundCreateDTO dto) {
        paymentFacade.refund(dto);
        return Result.build(null);
    }

    @Operation(summary = "获取所有支付方式")
    @GetMapping("/methods")
    public Result<PayTypeEnum[]> getPayMethods() {
        return Result.build(PayTypeEnum.values());
    }
}
