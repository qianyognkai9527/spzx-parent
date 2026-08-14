package com.joker.spzx.model.vo.mall;

import lombok.Data;

@Data
public class VisualScoreStatsVo {

    private Integer total;

    private Integer unscored;

    private Double avgScore;

    private Integer countS;

    private Integer countAPlus;

    private Integer countA;

    private Integer countB;

    private Integer countC;

    private Integer countD;

    private Integer countDMinus;
}
