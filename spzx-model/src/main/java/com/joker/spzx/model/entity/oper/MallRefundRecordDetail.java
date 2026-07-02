package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;

/**
 * <p>
 * 退款报表详情
 * </p>
 *
 * @author joker
 * @since 2025-07-11 10:38:11
 */
@Getter
@Setter
@TableName("mall_refund_record_detail")
@Schema(name = "MallRefundRecordDetail", description = "退款报表详情")
public class MallRefundRecordDetail extends Model<MallRefundRecordDetail> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "报表名称")
    @TableField("record_id")
    private Long recordId;

    @Schema(description = "总订单数")
    @TableField("total_count")
    private Integer totalCount;

    @Schema(description = "成功订单数")
    @TableField("success_count")
    private Integer successCount;

    @Schema(description = "退款订单数")
    @TableField("refund_count")
    private Integer refundCount;

    @Schema(description = "待定订单数")
    @TableField("pending_count")
    private Integer pendingCount;

    @Schema(description = "刷单订单数")
    @TableField("brush_count")
    private Integer brushCount;

    @Schema(description = "成功订单金额")
    @TableField("success_money")
    private BigDecimal successMoney;

    @Schema(description = "退款订单金额")
    @TableField("refund_money")
    private BigDecimal refundMoney;

    @Schema(description = "待定订单金额")
    @TableField("pending_money")
    private BigDecimal pendingMoney;

    @Schema(description = "刷单订单金额")
    @TableField("brush_money")
    private BigDecimal brushMoney;

    @Schema(description = "刷单订单其他金额(佣金运费等)")
    @TableField("brush_other_money")
    private BigDecimal brushOtherMoney;

    @Schema(description = "当前退款率")
    @TableField("current_refund_rate")
    private BigDecimal currentRefundRate;

    @Schema(description = "乐观退款率")
    @TableField("optimist_refund_rate")
    private BigDecimal optimistRefundRate;

    @Schema(description = "悲观退款率")
    @TableField("pessimist_refund_rate")
    private BigDecimal pessimistRefundRate;

    @Schema(description = "盈利金额")
    @TableField("profit_amount")
    private BigDecimal profitAmount;

    @Schema(description = "总支付金额")
    @TableField("total_pay_amount")
    private BigDecimal totalPayAmount;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;
}
