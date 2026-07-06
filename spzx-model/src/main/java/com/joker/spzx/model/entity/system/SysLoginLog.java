package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("sys_login_log")
@Schema(name = "SysLoginLog", description = "登录日志表")
public class SysLoginLog {

    @Schema(description = "主键ID")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "用户ID")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "用户名或微信昵称")
    @TableField("username")
    private String username;

    @Schema(description = "登录方式(1密码 2微信扫码)")
    @TableField("login_type")
    private Integer loginType;

    @Schema(description = "登录状态(1成功 0失败)")
    @TableField("login_status")
    private Integer loginStatus;

    @Schema(description = "微信OpenID")
    @TableField("openid")
    private String openid;

    @Schema(description = "客户端IP")
    @TableField("ip_address")
    private String ipAddress;

    @Schema(description = "User-Agent")
    @TableField("user_agent")
    private String userAgent;

    @Schema(description = "登录地点")
    @TableField("location")
    private String location;

    @Schema(description = "失败原因")
    @TableField("fail_reason")
    private String failReason;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Schema(description = "登录时间")
    @TableField("create_time")
    private LocalDateTime createTime;
}
