package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("profit_analysis_record")
@Schema(name = "ProfitAnalysisRecord", description = "利润分析记录")
public class ProfitAnalysisRecord extends BaseEntity {

    @Schema(description = "商品ID")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "商品标题")
    @TableField("product_title")
    private String productTitle;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "售价")
    @TableField("price")
    private BigDecimal price;

    @Schema(description = "货源价/成本")
    @TableField("cost")
    private BigDecimal cost;

    @Schema(description = "发出运费")
    @TableField("freight")
    private BigDecimal freight;

    @Schema(description = "退回运费")
    @TableField("return_freight")
    private BigDecimal returnFreight;

    @Schema(description = "运费险保费/单")
    @TableField("freight_insurance")
    private BigDecimal freightInsurance;

    @Schema(description = "运费险理赔额")
    @TableField("insurance_cover")
    private BigDecimal insuranceCover;

    @Schema(description = "推广费/单")
    @TableField("ad_cost")
    private BigDecimal adCost;

    @Schema(description = "平台佣金率%")
    @TableField("commission_rate")
    private BigDecimal commissionRate;

    @Schema(description = "支付手续费率%")
    @TableField("payment_fee_rate")
    private BigDecimal paymentFeeRate;

    @Schema(description = "预估退款率%")
    @TableField("refund_rate")
    private BigDecimal refundRate;

    @Schema(description = "预估订单量")
    @TableField("order_count")
    private Integer orderCount;

    @Schema(description = "单笔净利")
    @TableField("per_order_net_avg")
    private BigDecimal perOrderNetAvg;

    @Schema(description = "ROI")
    @TableField("roi")
    private BigDecimal roi;

    @Schema(description = "ROAS")
    @TableField("roas")
    private BigDecimal roas;

    @Schema(description = "盈亏平衡推广出价")
    @TableField("break_even_ad_cost")
    private BigDecimal breakEvenAdCost;

    @Schema(description = "盈亏平衡退款率%")
    @TableField("break_even_refund_rate")
    private BigDecimal breakEvenRefundRate;

    @Schema(description = "盈亏平衡售价")
    @TableField("break_even_price")
    private BigDecimal breakEvenPrice;

    @Schema(description = "预估总利润")
    @TableField("actual_total_profit")
    private BigDecimal actualTotalProfit;

    @Schema(description = "单笔毛利")
    @TableField("gross_profit_per_order")
    private BigDecimal grossProfitPerOrder;

    @Schema(description = "净利率%")
    @TableField("net_margin")
    private BigDecimal netMargin;

    @Schema(description = "是否建议投放：0-否, 1-是")
    @TableField("can_promote")
    private Integer canPromote;

    // 综合模型新增字段
    @Schema(description = "选货运费")
    @TableField("sourcing_freight")
    private BigDecimal sourcingFreight;

    @Schema(description = "付费订单占比%")
    @TableField("paid_ratio")
    private BigDecimal paidRatio;

    @Schema(description = "成本回收率%")
    @TableField("cost_recovery_rate")
    private BigDecimal costRecoveryRate;

    @Schema(description = "付费订单数")
    @TableField("paid_orders")
    private Integer paidOrders;

    @Schema(description = "自然订单数")
    @TableField("organic_orders")
    private Integer organicOrders;

    @Schema(description = "创建人")
    @TableField("create_by")
    private String createBy;

}
