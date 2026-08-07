package com.joker.spzx.model.dto.product;

import com.joker.spzx.model.dto.system.PageParam;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "商品搜索条件实体类")
public class ProductDto extends PageParam {

    @Schema(description = "货源商品标题")
    private String sourceProductName;

    @Schema(description = "货源商品Id")
    private String sourceProductCode;

    @Schema(description = "货源工厂Id")
    private Long productFactoryId;

    @Schema(description = "三级分类id")
    private Integer steadyStatus;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;

    @Schema(description = "数据来源:1=1688搜索候选 2=ISV已铺货")
    private Integer dataSource;

    @Schema(description = "优质等级:A/B/C(筛选)")
    private String qualityGrade;

    @Schema(description = "类目(爬虫)")
    private String categoryName;

    @Schema(description = "供应商名称(爬虫,模糊)")
    private String supplierName;

}
