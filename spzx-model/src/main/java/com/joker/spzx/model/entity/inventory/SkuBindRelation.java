package com.joker.spzx.model.entity.inventory;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.Date;

/**
 * SKU级关联表（平台SKU ↔ 货源SKU）
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("sku_bind_relation")
public class SkuBindRelation extends BaseEntity {

    private Long platformSkuId;

    private Long sourceSkuId;

    private Integer status;

    private String matchType;

    private Long confirmBy;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date confirmTime;
}
