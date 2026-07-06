package com.joker.spzx.model.vo.system;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "微信绑定信息响应")
public class WxLoginBindInfoVo {

    @Schema(description = "是否已绑定微信")
    private Boolean binded;

    @Schema(description = "微信昵称")
    private String nickname;

    @Schema(description = "微信头像URL")
    private String avatarUrl;

    @Schema(description = "绑定时间")
    private String bindTime;
}
