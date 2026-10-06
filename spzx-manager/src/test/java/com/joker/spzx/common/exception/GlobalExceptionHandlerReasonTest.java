package com.joker.spzx.common.exception;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * 用错接口时的文案 —— 纯函数，不拉 Spring。
 *
 * 这几类以前全落 catch-all，界面统一显示"您的网络有问题请稍后重试"：
 * 前端少传一个参数会被当成网络故障排查半天，日志里还留一条 ERROR 全栈冒充系统崩了。
 * 另一件要守的是别把请求体原文回显出去——坏 JSON 的 message 里带着 body，登录体里有口令。
 */
class GlobalExceptionHandlerReasonTest {

    @Test
    void 少传必填参数要点名是哪个参数() {
        assertEquals("缺少必填参数：platformType", GlobalExceptionHandler.reasonFor(
                new MissingServletRequestParameterException("platformType", "Integer")));
    }

    @Test
    void 参数类型不对要点名是哪个参数() {
        assertEquals("参数类型不对：pageNum", GlobalExceptionHandler.reasonFor(
                new MethodArgumentTypeMismatchException("abc", Integer.class, "pageNum", null, null)));
    }

    @Test
    void 坏请求体只说不合法不回显内容() {
        String reason = GlobalExceptionHandler.reasonFor(new HttpMessageNotReadableException(
                "JSON parse error: Unexpected character ... at [Source: (byte[])\"{\\\"password\\\":\\\"123456\\\"}\n]"));
        assertEquals("请求体不是合法 JSON", reason);
        assertFalse(reason.contains("123456"));
    }

    @Test
    void 路径不存在不说成网络问题() {
        assertEquals("接口不存在", GlobalExceptionHandler.reasonFor(
                new NoResourceFoundException(HttpMethod.GET, "admin/ingest/freshness/health")));
    }

    /** GET 接口被用 POST 打：这是调用方用错，不是系统崩了（2026-10-06 我自己踩出来的一次 9999） */
    @Test
    void 方法用错要点名方法并说明支持什么() {
        HttpRequestMethodNotSupportedException wrong =
                new HttpRequestMethodNotSupportedException("POST", java.util.List.of("GET"));
        String reason = GlobalExceptionHandler.reasonFor(wrong);
        assertEquals("请求方法 POST 不被该接口支持，该接口支持 GET", reason);
        assertFalse(reason.contains("网络"));
    }

    /** 拿不到支持列表时也不能吐 "null" 这种半句话 */
    @Test
    void 方法用错没有支持列表时只说前半句() {
        String reason = GlobalExceptionHandler.reasonFor(
                new HttpRequestMethodNotSupportedException("DELETE"));
        assertEquals("请求方法 DELETE 不被该接口支持", reason);
    }
}
