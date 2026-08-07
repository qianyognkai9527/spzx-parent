package com.joker.spzx.model.dto.product;

import com.joker.spzx.model.dto.system.PageParam;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "爬虫工厂排行榜分页查询参数")
public class SourceFactoryPageParam extends PageParam {

    @Schema(description = "厂家名称(模糊)")
    private String factoryName;

    @Schema(description = "主类目")
    private String categoryName;

    @Schema(description = "平台类型:1淘宝2抖音")
    private Integer platformType;

    @Schema(description = "优质等级:A/B(筛选)")
    private String qualityGrade;

    @Schema(description = "排序字段:avgRepurchaseRate/trustYears/productCount/totalSales")
    private String sortField;

    @Schema(description = "排序方向:asc/desc")
    private String sortOrder;
}
