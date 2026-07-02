package com.joker.spzx.model.dto.order;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "搜索条件实体类")
public class OrderStatisticsDto {

    @Schema(description = "开始时间")
    private String createTimeBegin;

    @Schema(description = "结束时间")
    private String createTimeEnd;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;

}
