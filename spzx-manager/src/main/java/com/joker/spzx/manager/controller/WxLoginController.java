package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.WxLoginService;
import com.joker.spzx.model.dto.system.WxLoginBindDto;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.system.WxLoginBindInfoVo;
import com.joker.spzx.model.vo.system.WxLoginCreateVo;
import com.joker.spzx.model.vo.system.WxLoginStatusVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@Tag(name = "微信扫码登录接口")
@RestController
@RequestMapping("/admin/system/index/wxLogin")
public class WxLoginController {

    @Autowired
    private WxLoginService wxLoginService;

    @PostMapping("/create")
    @Operation(summary = "生成扫码登录二维码")
    public Result<WxLoginCreateVo> create(HttpServletRequest request) {
        String clientIp = getClientIp(request);
        WxLoginCreateVo vo = wxLoginService.createQrLogin(clientIp);
        return Result.build(vo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/status")
    @Operation(summary = "轮询扫码登录状态")
    public Result<WxLoginStatusVo> status(@RequestParam String ticket) {
        WxLoginStatusVo vo = wxLoginService.getQrLoginStatus(ticket);
        return Result.build(vo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/callback")
    @Operation(summary = "微信授权回调")
    public String callback(@RequestParam String code, @RequestParam String state) {
        return wxLoginService.handleWxCallback(code, state);
    }

    @PostMapping("/bind")
    @Operation(summary = "绑定本地账号")
    public Result<WxLoginStatusVo> bind(@Valid @RequestBody WxLoginBindDto dto, HttpServletRequest request) {
        String clientIp = getClientIp(request);
        WxLoginStatusVo vo = wxLoginService.bindAccount(dto, clientIp);
        return Result.build(vo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/unbind")
    @Operation(summary = "解绑微信")
    public Result<Object> unbind() {
        wxLoginService.unbind();
        return Result.build(null);
    }

    @GetMapping("/bindInfo")
    @Operation(summary = "查询微信绑定信息")
    public Result<WxLoginBindInfoVo> bindInfo() {
        WxLoginBindInfoVo vo = wxLoginService.getBindInfo();
        return Result.build(vo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/mockScan")
    @Operation(summary = "Mock模拟扫码")
    public Result<Object> mockScan(@RequestParam String ticket) {
        wxLoginService.mockScan(ticket);
        return Result.build(null);
    }

    @GetMapping("/mockConfirm")
    @Operation(summary = "Mock模拟确认登录")
    public String mockConfirm(@RequestParam String ticket) {
        wxLoginService.mockConfirm(ticket);
        return "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='text-align:center;padding-top:80px;font-family:sans-serif'>"
                + "<h2 style='color:#67c23a'>✅ 模拟扫码确认成功</h2>"
                + "<p>请返回登录页面，系统将自动登录</p>"
                + "<script>setTimeout(()=>window.close(),3000)</script>"
                + "</body></html>";
    }

    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("X-Real-IP");
        }
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }
}
