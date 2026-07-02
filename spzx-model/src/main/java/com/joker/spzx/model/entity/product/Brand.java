package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("brand")
@Schema(name = "Brand", description = "分类品牌")
public class Brand extends BaseEntity {

    @Schema(description = "品牌名称")
    @TableField("name")
    private String name;

    @Schema(description = "品牌图标")
    @TableField("logo")
    private String logo;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;
}