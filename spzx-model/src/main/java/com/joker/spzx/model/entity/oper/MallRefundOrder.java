package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * <p>
 * excel订单数据
 * </p>
 *
 * @author joker
 * @since 2025-07-10 14:04:10
 */
@Getter
@Setter
@TableName("mall_refund_order")
@Schema(name = "MallRefundOrder", description = "excel订单数据")
public class MallRefundOrder extends Model<MallRefundOrder> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "所属excel文件编码")
    @TableField("code")
    private String code;

    @Schema(description = "报表名称")
    @TableField("order_id")
    private String orderId;

    @Schema(description = "实付金额")
    @TableField("pay_money")
    private BigDecimal payMoney;

    @Schema(description = "退款金额")
    @TableField("refund_money")
    private BigDecimal refundMoney;

    @Schema(description = "状态（1：未生成2：生成中3：已生成")
    @TableField("order_status")
    private String orderStatus;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
