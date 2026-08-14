package com.joker.spzx.model.vo.mall;

import lombok.Data;

@Data
public class VisualScoreImgVo {

    private Long productId;

    private Long mediaId;

    private Integer imgPos;

    private String fileUrl;

    private Integer visualScore;

    private String grade;
}
