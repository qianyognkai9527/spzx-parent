package com.joker.spzx.common.exception;

import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(Exception.class)
    public Result error(Exception e) {
        log.error("系统异常", e);
        return Result.build(null, ResultCodeEnum.SYSTEM_ERROR);
    }

    /**
     * 调用方用错接口的五类（少传必填参数、参数类型不对、请求体不是合法 JSON、路径不存在、方法用错）
     * 以前统统掉进上面的 catch-all：界面显示"您的网络有问题请稍后重试"，日志落一条 ERROR 全栈。
     * 明明是接口用错了却报成网络故障，还会把"后端日志 0 ERROR"这类健康判据冲淡。
     *
     * 只回显我们自己拼的原因，不打 e.getMessage()：HttpMessageNotReadableException 的 message
     * 里带着请求体原文（登录请求的体里有口令），MethodArgumentTypeMismatch 的 message 里带着用户输入。
     * 日志里的路径用 getRequestURI()，不含 query string，避免把任意输入写进日志。
     */
    @ExceptionHandler({MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class,
            HttpMessageNotReadableException.class,
            NoResourceFoundException.class,
            HttpRequestMethodNotSupportedException.class})
    public Result handleBadCall(Exception e, HttpServletRequest request) {
        String reason = reasonFor(e);
        log.warn("请求错误 {} {} -> {} ({})", request.getMethod(), request.getRequestURI(),
                reason, e.getClass().getSimpleName());
        return Result.build(null, 400, reason);
    }

    static String reasonFor(Exception e) {
        if (e instanceof MissingServletRequestParameterException missing) {
            return "缺少必填参数：" + missing.getParameterName();
        }
        if (e instanceof MethodArgumentTypeMismatchException mismatch) {
            return "参数类型不对：" + mismatch.getName();
        }
        if (e instanceof HttpMessageNotReadableException) {
            return "请求体不是合法 JSON";
        }
        if (e instanceof NoResourceFoundException) {
            return "接口不存在";
        }
        if (e instanceof HttpRequestMethodNotSupportedException wrong) {
            String allow = supportedMethods(wrong);
            return "请求方法 " + wrong.getMethod() + " 不被该接口支持"
                    + (allow.isEmpty() ? "" : "，该接口支持 " + allow);
        }
        return "请求错误";
    }

    /** 支持列表两个来源都要试：新 ctor 填 HttpMethods，老 ctor 只填 String[] */
    private static String supportedMethods(HttpRequestMethodNotSupportedException wrong) {
        var methods = wrong.getSupportedHttpMethods();
        if (methods != null && !methods.isEmpty()) {
            return methods.stream().map(String::valueOf).sorted().reduce((a, b) -> a + "/" + b).orElse("");
        }
        String[] raw = wrong.getSupportedMethods();
        return raw == null || raw.length == 0 ? "" : String.join("/", raw);
    }

    @ExceptionHandler(value = ServiceException.class)
    public Result<String> error(ServiceException exception) {
        log.error("业务异常: {}", exception.getMessage());
        if (exception.getResultCodeEnum() != null) {
            return Result.build(exception.getMessage(), exception.getResultCodeEnum());
        }
        return Result.build(null, exception.getCode(), exception.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<String> handleValidException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        log.warn("参数校验失败: {}", message);
        return Result.build(null, 400, message);
    }

    @ExceptionHandler(BindException.class)
    public Result<String> handleBindException(BindException e) {
        String message = e.getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        log.warn("参数绑定失败: {}", message);
        return Result.build(null, 400, message);
    }
}