package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("product_sku")
@Schema(name = "ProductSku", description = "商品sku")
public class ProductSku extends BaseEntity {


    @Schema(description = "商品编号")
    @TableField("sku_code")
    private String skuCode;

    @TableField("sku_name")
    private String skuName;

    @Schema(description = "商品ID")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "缩略图路径")
    @TableField("thumb_img")
    private String thumbImg;

    @Schema(description = "售价")
    @TableField("sale_price")
    private BigDecimal salePrice;

    @Schema(description = "市场价")
    @TableField("market_price")
    private BigDecimal marketPrice;

    @Schema(description = "成本价")
    @TableField("cost_price")
    private BigDecimal costPrice;

    @Schema(description = "库存数")
    @TableField("stock_num")
    private Integer stockNum;

    @Schema(description = "销量")
    @TableField("sale_num")
    private Integer saleNum;

    @Schema(description = "sku规格信息json")
    @TableField("sku_spec")
    private String skuSpec;

    @Schema(description = "重量")
    @TableField("weight")
    private BigDecimal weight;

    @Schema(description = "体积")
    @TableField("volume")
    private BigDecimal volume;

    @Schema(description = "线上状态：0-初始值，1-上架，-1-自主下架")
    @TableField("status")
    private Integer status;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}