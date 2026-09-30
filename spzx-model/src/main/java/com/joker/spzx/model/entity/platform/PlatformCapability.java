package com.joker.spzx.model.entity.platform;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

/**
 * 平台能力矩阵。
 * 真主键为联合主键 (platform_code, capability)，MyBatis-Plus 不支持复合主键，
 * 因此本实体不加 @TableId：只用于 selectList 查询，勿调用 selectById/updateById/deleteById。
 */
@Getter
@Setter
@TableName("platform_capability")
@Schema(name = "PlatformCapability", description = "平台能力矩阵")
public class PlatformCapability {

    @Schema(description = "平台编码：1-淘宝, 2-抖音, 3-拼多多")
    @TableField("platform_code")
    private Integer platformCode;

    @Schema(description = "能力标识：ingest_order/ingest_item/publish_product 等")
    @TableField("capability")
    private String capability;

    @Schema(description = "是否支持：1-支持 0-不支持")
    @TableField("supported")
    private Integer supported;

    @Schema(description = "实现通道：browser/api 等，null 表示平台默认")
    @TableField("channel")
    private String channel;

    @Schema(description = "备注")
    @TableField("note")
    private String note;
}
