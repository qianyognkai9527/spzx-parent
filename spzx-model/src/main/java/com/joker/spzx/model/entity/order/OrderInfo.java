package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Data
@TableName("order_info")
@Schema(name = "OrderInfo", description = "订单")
public class OrderInfo extends BaseEntity {

    @Schema(description = "会员_id")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "昵称")
    @TableField("nick_name")
    private String nickName;

    @Schema(description = "订单号")
    @TableField("order_no")
    private String orderNo;

    @Schema(description = "使用的优惠券")
    @TableField("coupon_id")
    private Long couponId;

    @Schema(description = "订单总额")
    @TableField("total_amount")
    private BigDecimal totalAmount;

    @Schema(description = "优惠券")
    @TableField("coupon_amount")
    private BigDecimal couponAmount;

    @Schema(description = "原价金额")
    @TableField("original_total_amount")
    private BigDecimal originalTotalAmount;

    @Schema(description = "运费")
    @TableField("feight_fee")
    private BigDecimal feightFee;

    @Schema(description = "支付方式【1->微信 2->支付宝】")
    @TableField("pay_type")
    private Byte payType;

    @Schema(description = "订单状态【0->待付款；1->待发货；2->已发货；3->待用户收货，已完成；-1->已取消】")
    @TableField("order_status")
    private Byte orderStatus;

    @Schema(description = "收货人姓名")
    @TableField("receiver_name")
    private String receiverName;

    @Schema(description = "收货人电话")
    @TableField("receiver_phone")
    private String receiverPhone;

    @Schema(description = "收货人地址标签")
    @TableField("receiver_tag_name")
    private String receiverTagName;

    @Schema(description = "省份/直辖市")
    @TableField("receiver_province")
    private Long receiverProvince;

    @Schema(description = "城市")
    @TableField("receiver_city")
    private Long receiverCity;

    @Schema(description = "区")
    @TableField("receiver_district")
    private Long receiverDistrict;

    @Schema(description = "详细地址")
    @TableField("receiver_address")
    private String receiverAddress;

    @Schema(description = "支付时间")
    @TableField("payment_time")
    private LocalDateTime paymentTime;

    @Schema(description = "发货时间")
    @TableField("delivery_time")
    private LocalDateTime deliveryTime;

    @Schema(description = "确认收货时间")
    @TableField("receive_time")
    private LocalDateTime receiveTime;

    @Schema(description = "订单备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "取消订单时间")
    @TableField("cancel_time")
    private LocalDateTime cancelTime;

    @Schema(description = "取消订单原因")
    @TableField("cancel_reason")
    private String cancelReason;

    @Schema(description = "订单项列表")
    private List<OrderItem> orderItemList;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}