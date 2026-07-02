package com.joker.spzx.model.dto.mall;


import lombok.Data;

@Data
public class FarmOrderPageDto {

    Integer pageNum;
    Integer pageSize;
    Long productId;
    Integer status;
    Integer platformType;

}
