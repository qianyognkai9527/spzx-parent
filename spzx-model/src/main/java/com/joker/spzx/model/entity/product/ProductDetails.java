package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("product_details")
@Schema(name = "ProductDetails", description = "商品sku属性表")
public class ProductDetails extends BaseEntity {

    @Schema(description = "商品id")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "详情图片地址")
    @TableField("image_urls")
    private String imageUrls;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}