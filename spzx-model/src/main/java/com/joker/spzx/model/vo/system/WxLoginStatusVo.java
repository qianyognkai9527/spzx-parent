package com.joker.spzx.model.vo.system;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "微信扫码登录轮询状态响应")
public class WxLoginStatusVo {

    @Schema(description = "票据状态(0待扫描 1已扫描 2已确认 3已过期 4已取消 5需绑定)")
    private Integer status;

    @Schema(description = "状态描述")
    private String message;

    @Schema(description = "登录令牌(状态为2时返回)")
    private String token;

    @Schema(description = "票据(状态为5时返回,用于绑定接口)")
    private String ticket;
}
