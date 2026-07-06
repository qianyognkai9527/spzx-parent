package com.joker.spzx.common.exception;

import com.joker.spzx.model.vo.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(Exception.class)
    public Result error(Exception e) {
        log.error("系统异常", e);
        return Result.build(null, 201, "出现了异常");
    }

    @ExceptionHandler(value = ServiceException.class)
    public Result<String> error(ServiceException exception) {
        log.error("业务异常: {}", exception.getMessage());
        return Result.build(exception.getMessage(), exception.getResultCodeEnum());
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