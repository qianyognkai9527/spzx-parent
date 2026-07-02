package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * <p>
 * 优惠券信息
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Getter
@Setter
@TableName("coupon_info")
@Schema(name = "CouponInfo", description = "优惠券信息")
public class CouponInfo extends BaseEntity {

    @Schema(description = "购物券类型 1 现金券 2 满减券")
    @TableField("coupon_type")
    private Integer couponType;

    @Schema(description = "优惠卷名字")
    @TableField("coupon_name")
    private String couponName;

    @Schema(description = "金额")
    @TableField("amount")
    private BigDecimal amount;

    @Schema(description = "使用门槛 0->没门槛")
    @TableField("condition_amount")
    private BigDecimal conditionAmount;

    @Schema(description = "可以领取的开始日期")
    @TableField("start_time")
    private LocalDate startTime;

    @Schema(description = "可以领取的结束日期")
    @TableField("end_time")
    private LocalDate endTime;

    @Schema(description = "使用范围[1->全场通用；2->指定分类；3->指定商品]")
    @TableField("range_type")
    private Integer rangeType;

    @Schema(description = "使用范围描述")
    @TableField("range_desc")
    private String rangeDesc;

    @Schema(description = "发行数量")
    @TableField("publish_count")
    private Integer publishCount;

    @Schema(description = "每人限领张数")
    @TableField("per_limit")
    private Integer perLimit;

    @Schema(description = "已使用数量")
    @TableField("use_count")
    private Integer useCount;

    @Schema(description = "领取数量")
    @TableField("receive_count")
    private Integer receiveCount;

    @Schema(description = "过期时间")
    @TableField("expire_time")
    private LocalDateTime expireTime;

    @Schema(description = "发布状态[0-未发布，1-已发布]")
    @TableField("publish_status")
    private Boolean publishStatus;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}
