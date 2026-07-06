package com.joker.spzx.model.vo.system;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "微信扫码登录生成票据响应")
public class WxLoginCreateVo {

    @Schema(description = "票据(前端轮询凭证)")
    private String ticket;

    @Schema(description = "微信授权URL(前端用于生成二维码)")
    private String wxAuthUrl;
}
