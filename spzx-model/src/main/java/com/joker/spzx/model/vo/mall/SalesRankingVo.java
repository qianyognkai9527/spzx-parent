package com.joker.spzx.model.vo.mall;

import lombok.Data;

@Data
public class SalesRankingVo {

    private Long sourceProductId;

    private String sourceProductName;

    private String sourceProductCode;

    private String headImgUrl;

    private String categoryName;

    private String qualityGrade;

    private Long sold;

    private Long restocked;

    private Long netChange;

    private Integer changeCount;

    private String lastChangeTime;
}
