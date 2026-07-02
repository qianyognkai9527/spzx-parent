package com.joker.spzx.model.entity.system;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 优惠券范围表
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Getter
@Setter
@TableName("coupon_range")
@Schema(name = "CouponRange", description = "优惠券范围表")
public class CouponRange extends BaseEntity {


    @Schema(description = "优惠券id")
    @TableField("coupon_id")
    private Long couponId;

    @Schema(description = "范围类型； 1->商品(sku) ；2->分类")
    @TableField("range_type")
    private Integer rangeType;

    @TableField("range_id")
    private Long rangeId;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}
