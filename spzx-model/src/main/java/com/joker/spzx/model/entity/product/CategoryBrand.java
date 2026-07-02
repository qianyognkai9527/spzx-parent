package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("category_brand")
@Schema(name = "CategoryBrand", description = "分类品牌")
public class CategoryBrand extends BaseEntity {

    @Schema(description = "品牌ID")
    @TableField("brand_id")
    private Long brandId;

    @Schema(description = "分类ID")
    @TableField("category_id")
    private Long categoryId;

    @Schema(description = "分类名称", required = false)
    @TableField(exist = false)
    private String categoryName;

    @Schema(description = "品牌名称", required = false)
    @TableField(exist = false)
    private String brandName;

    @Schema(description = "品牌logo", required = false)
    @TableField(exist = false)
    private String logo;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}