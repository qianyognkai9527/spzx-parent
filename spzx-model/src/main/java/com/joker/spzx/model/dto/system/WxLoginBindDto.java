package com.joker.spzx.model.dto.system;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
@Schema(description = "微信扫码登录绑定账号请求")
public class WxLoginBindDto {

    @NotBlank(message = "票据不能为空")
    @Schema(description = "扫码票据")
    private String ticket;

    @NotBlank(message = "用户名不能为空")
    @Schema(description = "本地系统用户名")
    private String userName;

    @NotBlank(message = "密码不能为空")
    @Schema(description = "本地系统密码")
    private String password;
}
