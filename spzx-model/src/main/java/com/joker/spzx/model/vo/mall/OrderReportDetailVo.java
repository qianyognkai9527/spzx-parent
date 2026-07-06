package com.joker.spzx.model.vo.mall;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Data
@Schema(description = "订单报表详情VO")
public class OrderReportDetailVo {

    @Schema(description = "报表ID")
    private Long id;

    @Schema(description = "报表编码")
    private String code;

    @Schema(description = "报表名称")
    private String name;

    @Schema(description = "关联订单文件编码")
    private String orderDataCode;

    @Schema(description = "状态")
    private Integer state;

    @Schema(description = "开始时间")
    private LocalDateTime startTime;

    @Schema(description = "结束时间")
    private LocalDateTime endTime;

    @Schema(description = "统计卡片列表")
    private List<ReportStatCardVo> statCards;

    @Schema(description = "总支付金额")
    private BigDecimal totalPayAmount;

    @Schema(description = "盈利金额")
    private BigDecimal profitAmount;

    @Schema(description = "支付总金额")
    private BigDecimal totalAmount;

    @Schema(description = "智能推广花费")
    private BigDecimal smartPromotion;

    @Schema(description = "人群推广花费")
    private BigDecimal crowdPromotion;

    @Schema(description = "全站推广花费")
    private BigDecimal sitePromotion;

    @Schema(description = "关键词推广花费")
    private BigDecimal keywordPromotion;
}
