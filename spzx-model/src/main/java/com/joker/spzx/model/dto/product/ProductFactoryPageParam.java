package com.joker.spzx.model.dto.product;

import com.joker.spzx.model.dto.system.PageParam;
import lombok.Data;

@Data
public class ProductFactoryPageParam extends PageParam {

    private String factoryName;
    private Integer platformType;
}
