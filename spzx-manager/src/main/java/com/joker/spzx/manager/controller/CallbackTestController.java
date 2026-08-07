package com.joker.spzx.manager.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

/**
 * 回调测试接口 — 模拟外部服务回调场景
 * <p>
 * 通过 delay 参数控制服务端处理延迟，用于测试调用方的 connectTimeout / readTimeout。
 * 回调成功后返回纯文本 "success"。
 * </p>
 */
@Slf4j
@Tag(name = "回调测试", description = "模拟外部服务回调，支持超时测试")
@RestController
@RequestMapping("/api/test/callback")
public class CallbackTestController {

    @Operation(summary = "模拟回调（支持延迟）")
    @PostMapping("/{delay}")
    public String callback(
            @Parameter(description = "延迟秒数，用于模拟 readTimeout") @PathVariable int delay,
            @Parameter(description = "请求体（可选）") @RequestBody(required = false) String body) {

        log.info("收到回调测试请求，delay={}s，body={}", delay, body);

        if (delay > 0) {
            try {
                Thread.sleep(delay * 1000L);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                log.warn("延迟被中断", e);
                return "success";
            }
        }

        log.info("回调测试处理完成，返回 success");
        return "success";
    }

    @Operation(summary = "模拟回调（无延迟）")
    @PostMapping
    public String callbackNoDelay(@RequestBody(required = false) String body) {
        log.info("收到回调测试请求（无延迟），body={}", body);
        return "success";
    }
}
