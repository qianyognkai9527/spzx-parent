package com.joker.spzx.model.dto.product;


import lombok.Data;

@Data
public class ProductBindQueryDto {

    private String sourceProductName;
    private String sourceProductCode;
    private Long productFactoryId;

    private Integer platformType;
}
