package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.util.List;

@Data
public class VariantSetVo {

    private Integer variantSet;

    private Integer platformType;

    private List<VariantItemVo> items;
}
