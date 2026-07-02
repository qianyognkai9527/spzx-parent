package com.joker.spzx.model.entity.pay;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("payment_info")
@Schema(name = "PaymentInfo", description = "付款信息表")
public class PaymentInfo extends BaseEntity {

    @Schema(description = "用户id")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "订单号")
    @TableField("order_no")
    private String orderNo;

    @Schema(description = "付款方式：1-微信 2-支付宝")
    @TableField("pay_type")
    private Byte payType;

    @Schema(description = "交易编号（微信或支付）")
    @TableField("out_trade_no")
    private String outTradeNo;

    @Schema(description = "支付金额")
    @TableField("amount")
    private BigDecimal amount;

    @Schema(description = "交易内容")
    @TableField("content")
    private String content;

    @Schema(description = "支付状态：0-未支付 1-已支付")
    @TableField("payment_status")
    private String paymentStatus;

    @Schema(description = "回调时间")
    @TableField("callback_time")
    private LocalDateTime callbackTime;

    @Schema(description = "回调信息")
    @TableField("callback_content")
    private String callbackContent;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}