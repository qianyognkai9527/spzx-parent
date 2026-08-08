package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "平台分布数据")
public class PlatformDistVo {

    @Schema(description = "平台类型:1-淘宝,2-抖音")
    private Integer platformType;

    @Schema(description = "平台名称")
    private String platformName;

    @Schema(description = "商品数")
    private Integer count;
}
