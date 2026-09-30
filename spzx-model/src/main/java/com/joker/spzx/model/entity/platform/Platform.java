package com.joker.spzx.model.entity.platform;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 平台注册表
 */
@Getter
@Setter
@TableName("platform")
@Schema(name = "Platform", description = "平台注册表")
public class Platform {

    @Schema(description = "平台编码：1-淘宝, 2-抖音, 3-拼多多")
    @TableId(value = "code", type = IdType.INPUT)
    private Integer code;

    @Schema(description = "平台标识：taobao/douyin/pinduoduo")
    @TableField("slug")
    private String slug;

    @Schema(description = "平台名称")
    @TableField("name")
    private String name;

    @Schema(description = "主题色，形如 #FF5000")
    @TableField("theme_color")
    private String themeColor;

    @Schema(description = "资金渠道")
    @TableField("money_channel")
    private String moneyChannel;

    @Schema(description = "是否启用：1-启用 0-停用")
    @TableField("enabled")
    private Integer enabled;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;
}
