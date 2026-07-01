package com.joker.spzx.common.exception;


import com.joker.spzx.model.vo.common.ResultCodeEnum;
import lombok.Getter;

@Getter
public class ServiceException extends RuntimeException {

    private Integer code ;          // 错误状态码
    private String message ;        // 错误消息

    private ResultCodeEnum resultCodeEnum ;     // 封装错误状态码和错误消息

    public ServiceException(ResultCodeEnum resultCodeEnum) {
        this.resultCodeEnum = resultCodeEnum ;
        this.code = resultCodeEnum.getCode() ;
        this.message = resultCodeEnum.getMessage();
    }

    public ServiceException(Integer code , String message) {
        this.code = code ;
        this.message = message ;
    }

}