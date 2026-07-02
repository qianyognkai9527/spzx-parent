package com.joker.spzx.model.dto.mall;


import lombok.Data;

import java.time.LocalDateTime;

@Data
public class BrushPersonDto {

    private Integer type;
    private String keyword;
    private LocalDateTime createTime;
    private LocalDateTime endTime;

    private Integer platformType;

}
