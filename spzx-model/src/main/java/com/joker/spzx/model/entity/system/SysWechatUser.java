package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_wechat_user")
@Schema(name = "SysWechatUser", description = "微信用户绑定表")
public class SysWechatUser extends BaseEntity {

    @Schema(description = "绑定的本地系统用户ID")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "微信OpenID")
    @TableField("openid")
    private String openid;

    @Schema(description = "微信UnionID")
    @TableField("unionid")
    private String unionid;

    @Schema(description = "微信应用AppID")
    @TableField("appid")
    private String appid;

    @Schema(description = "微信昵称")
    @TableField("nickname")
    private String nickname;

    @Schema(description = "微信头像URL")
    @TableField("avatar_url")
    private String avatarUrl;

    @Schema(description = "性别(0未知 1男 2女)")
    @TableField("sex")
    private Integer sex;

    @Schema(description = "国家")
    @TableField("country")
    private String country;

    @Schema(description = "省份")
    @TableField("province")
    private String province;

    @Schema(description = "城市")
    @TableField("city")
    private String city;

    @Schema(description = "绑定状态(1正常 0已解绑)")
    @TableField("bind_status")
    private Integer bindStatus;

    @Schema(description = "最后微信扫码登录时间")
    @TableField("last_login_time")
    private LocalDateTime lastLoginTime;

    @Schema(description = "最后登录IP")
    @TableField("last_login_ip")
    private String lastLoginIp;
}
