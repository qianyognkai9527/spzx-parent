package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.util.List;

@Data
public class VisualScoreVo {

    private Long mediaId;

    private Long productId;

    private String code;

    private String title;

    private Integer platformType;

    private List<VisualScoreImgVo> imgs;
}
