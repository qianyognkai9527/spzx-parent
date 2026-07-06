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
@TableName("sys_qr_login_ticket")
@Schema(name = "SysQrLoginTicket", description = "扫码登录票据表")
public class SysQrLoginTicket {

    @Schema(description = "主键ID")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "票据(UUID去横线)")
    @TableField("ticket")
    private String ticket;

    @Schema(description = "OAuth2 state(防CSRF)")
    @TableField("state")
    private String state;

    @Schema(description = "状态(0待扫描 1已扫描 2已确认 3已过期 4已取消 5需绑定)")
    @TableField("status")
    private Integer status;

    @Schema(description = "登录用户ID")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "扫码者OpenID")
    @TableField("openid")
    private String openid;

    @Schema(description = "发起扫码的PC端IP")
    @TableField("client_ip")
    private String clientIp;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Schema(description = "票据过期时间")
    @TableField("expire_time")
    private LocalDateTime expireTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;
}
