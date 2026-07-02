package com.joker.spzx.model.dto.mall;


import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class ProductPicVideoDto {

    private Long productId;

    private Long operId;

    private String takeDate;

    private Integer platformType;

    @NotNull
    @Size(min = 1)
    private List<PicVideoSimplerDto> picVideoSimplerDtoList;
}
