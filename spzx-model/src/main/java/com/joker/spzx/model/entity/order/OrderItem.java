package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("order_item")
@Schema(name = "OrderItem", description = "订单项信息")
public class OrderItem extends BaseEntity {

    private static final long serialVersionUID = 1L;

    @Schema(description = "order_id")
    @TableField("order_id")
    private Long orderId;

    @Schema(description = "商品sku编号")
    @TableField("sku_id")
    private Long skuId;

    @Schema(description = "商品sku名字")
    @TableField("sku_name")
    private String skuName;

    @Schema(description = "商品sku图片")
    @TableField("thumb_img")
    private String thumbImg;

    @Schema(description = "商品sku价格")
    @TableField("sku_price")
    private BigDecimal skuPrice;

    @Schema(description = "商品购买的数量")
    @TableField("sku_num")
    private Integer skuNum;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}