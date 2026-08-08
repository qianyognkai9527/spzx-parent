package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "工厂销量排行数据")
public class TopFactoryVo {

    @Schema(description = "厂家名称")
    private String factoryName;

    @Schema(description = "总销量")
    private Integer totalSales;

    @Schema(description = "优质等级")
    private String qualityGrade;

    @Schema(description = "主类目")
    private String categoryName;
}
