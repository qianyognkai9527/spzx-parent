package com.joker.spzx.model.entity.inventory;

import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

/**
 * 1688货源SKU快照
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("source_sku")
public class SourceSku extends BaseEntity {

    private Long sourceProductId;

    private String skuKey;

    private String skuId;

    private String specId;

    private Integer stock;

    private BigDecimal price;

    private Integer status;
}
