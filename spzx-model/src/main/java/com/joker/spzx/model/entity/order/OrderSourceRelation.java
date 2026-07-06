package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Schema(description = "本地订单与货源订单关联实体类")
public class OrderSourceRelation extends BaseEntity {

    @Schema(description = "本地订单号（淘宝/抖音订单号）")
    @TableField("order_no")
    private String orderNo;

    @Schema(description = "货源订单号")
    @TableField("source_order_no")
    private String sourceOrderNo;

    @Schema(description = "平台类型（1:淘宝 2:抖音）")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "平台商品ID")
    @TableField("platform_product_id")
    private Long platformProductId;

    @Schema(description = "平台商品编号")
    @TableField("platform_product_code")
    private String platformProductCode;

    @Schema(description = "平台商品标题")
    @TableField("platform_product_title")
    private String platformProductTitle;

    @Schema(description = "平台售价（定价）")
    @TableField("platform_selling_price")
    private BigDecimal platformSellingPrice;

    @Schema(description = "平台运费")
    @TableField("platform_freight")
    private BigDecimal platformFreight;

    @Schema(description = "货源商品ID")
    @TableField("source_product_id")
    private Long sourceProductId;

    @Schema(description = "货源商品编号")
    @TableField("source_product_code")
    private String sourceProductCode;

    @Schema(description = "货源商品标题")
    @TableField("source_product_title")
    private String sourceProductTitle;

    @Schema(description = "货源售价（进货价）")
    @TableField("source_selling_price")
    private BigDecimal sourceSellingPrice;

    @Schema(description = "货源运费")
    @TableField("source_freight")
    private BigDecimal sourceFreight;

    @Schema(description = "订单状态：1-待发货, 2-已发货, 3-已完成, 4-已取消")
    @TableField("order_status")
    private Integer orderStatus;

    @Schema(description = "下单时间")
    @TableField("order_time")
    private LocalDateTime orderTime;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

}
