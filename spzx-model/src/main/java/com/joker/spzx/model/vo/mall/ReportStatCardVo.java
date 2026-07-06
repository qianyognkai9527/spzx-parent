package com.joker.spzx.model.vo.mall;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "报表统计卡片VO")
public class ReportStatCardVo {

    @Schema(description = "卡片类型：total/brush/real/refund/pending/unknown")
    private String cardType;

    @Schema(description = "卡片标题")
    private String cardTitle;

    @Schema(description = "卡片数量")
    private Integer count;

    @Schema(description = "卡片金额")
    private BigDecimal amount;

    @Schema(description = "卡片颜色")
    private String color;

    @Schema(description = "图标")
    private String icon;
}
