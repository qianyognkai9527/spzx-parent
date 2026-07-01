package com.joker.spzx.common.exception;

import com.joker.spzx.model.vo.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

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
}