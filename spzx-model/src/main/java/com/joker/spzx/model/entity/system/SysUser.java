package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.ToString;

@Data
@ToString(exclude = "password")
@TableName("sys_user")
@Schema(name = "SysUser", description = "用户表")
public class SysUser extends BaseEntity {

    @Schema(description = "用户名")
    @TableField("username")
    private String username;

    @Schema(description = "密码")
    @TableField("password")
    @JsonProperty(access = JsonProperty.Access.WRITE_ONLY)
    private String password;

    @Schema(description = "姓名")
    @TableField("name")
    private String name;

    @Schema(description = "手机")
    @TableField("phone")
    private String phone;

    @Schema(description = "头像")
    @TableField("avatar")
    private String avatar;

    @Schema(description = "描述")
    @TableField("description")
    private String description;

    @Schema(description = "状态（1：正常 0：停用）")
    @TableField("status")
    private Integer status;

}