package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "商品规格实体类")
public class ProductSpec extends BaseEntity {

    @Schema(description = "规格名称")
    @TableField("spec_name")
    private String specName;

    @Schema(description = "规格值valueList蓝,白,红")
    @TableField("spec_value")
    private String specValue;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;
}