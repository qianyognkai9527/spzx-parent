package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * <p>
 * 优惠券领用表
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Getter
@Setter
@TableName("coupon_user")
@Schema(name = "CouponUser", description = "优惠券领用表")
public class CouponUser extends Model<CouponUser> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "编号")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "购物券ID")
    @TableField("coupon_id")
    private Long couponId;

    @Schema(description = "用户ID")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "订单ID")
    @TableField("order_id")
    private Long orderId;

    @Schema(description = "购物券状态（1：未使用 2：已使用）")
    @TableField("coupon_status")
    private Byte couponStatus;

    @Schema(description = "获取类型（1：后台赠送；2：主动获取）")
    @TableField("get_type")
    private Byte getType;

    @Schema(description = "获取时间")
    @TableField("get_time")
    private LocalDateTime getTime;

    @Schema(description = "使用时间")
    @TableField("using_time")
    private LocalDateTime usingTime;

    @Schema(description = "支付时间")
    @TableField("used_time")
    private LocalDateTime usedTime;

    @Schema(description = "过期时间")
    @TableField("expire_time")
    private LocalDateTime expireTime;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "删除标记（0:不可用 1:可用）")
    @TableField("is_deleted")
    private Byte isDeleted;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
