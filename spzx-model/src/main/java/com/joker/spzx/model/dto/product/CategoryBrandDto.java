package com.joker.spzx.model.dto.product;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "搜索条件实体类")
public class CategoryBrandDto {

    @Schema(description = "品牌id")
    private Long brandId;

    @Schema(description = "分类id")
    private Long categoryId;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;

}