package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.math.BigDecimal;

/** 低库存规格明细一行。sourceProductId 供 service 回填装配，前端忽略。 */
@Data
public class LowStockSpecVo {

    private Long sourceProductId;

    /** 规格名（source_sku.sku_key） */
    private String skuKey;

    private Integer stock;

    private BigDecimal price;
}
