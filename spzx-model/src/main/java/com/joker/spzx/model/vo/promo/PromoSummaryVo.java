package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 推广日报汇总卡片。
 *
 * 比率一律由**汇总后的分子/分母重算**，不是把每日百分比求平均 ——
 * 各天流量差一个数量级时，平均百分比会被小流量那天带偏。
 * 分子分母有一方为 0 或 null 时留 null（前端显示"未跑"），不写 0：
 * 0 表示"算出来是零"，null 表示"分母不存在，无从算"，两者混了就会把"没点击"读成"CPC 为零"。
 */
@Data
@Schema(description = "推广日报区间汇总")
public class PromoSummaryVo {

    @Schema(description = "区间起")
    private String dateFrom;

    @Schema(description = "区间止")
    private String dateTo;

    @Schema(description = "请求区间起（与 dateFrom/dateTo 不同即说明区间两端有日子缺报，看板要标出来）")
    private String rangeFrom;

    @Schema(description = "请求区间止")
    private String rangeTo;

    @Schema(description = "区间内有日报的天数（不是自然日数：没投放的那天报表里就没有行）")
    private Integer days;

    @Schema(description = "有花费的计划数")
    private Integer planCount;

    @Schema(description = "花费合计(元)")
    private BigDecimal charge;

    @Schema(description = "展现量合计")
    private Long adPv;

    @Schema(description = "点击量合计")
    private Long click;

    @Schema(description = "点击率 %（=点击/展现 重算）")
    private BigDecimal ctrPercent;

    @Schema(description = "平均点击花费(元)（=花费/点击 重算）")
    private BigDecimal cpc;

    @Schema(description = "千次展现花费(元)")
    private BigDecimal cpm;

    @Schema(description = "总成交金额(元)")
    private BigDecimal gmvTotal;

    @Schema(description = "直接成交金额(元)")
    private BigDecimal gmvDirect;

    @Schema(description = "总成交笔数")
    private Integer orderTotal;

    @Schema(description = "投入产出比（=总成交/花费 重算）")
    private BigDecimal roi;

    @Schema(description = "总购物车数")
    private Integer cartCount;

    @Schema(description = "总收藏数")
    private Integer collectTotal;

    @Schema(description = "区间内最后一次采集时间（用于判断数是不是新的）")
    private String lastCollectedAt;
}
