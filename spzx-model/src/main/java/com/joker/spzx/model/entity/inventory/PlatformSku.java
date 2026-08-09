package com.joker.spzx.model.entity.inventory;

import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 平台商品SKU快照
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("platform_sku")
public class PlatformSku extends BaseEntity {

    private Long platformProductId;

    private Integer platformType;

    private String skuKey;

    private String skuId;

    private String merchantCode;

    private Integer stock;
}
