package com.joker.spzx.model.vo.mall;

import lombok.Data;

@Data
public class EvalGapVo {

    private Long id;

    private String code;

    private String title;

    private String headImgUrl;

    private Integer platformEvalCount;

    private Integer sourceEvalCount;

    private Integer gap;
}
