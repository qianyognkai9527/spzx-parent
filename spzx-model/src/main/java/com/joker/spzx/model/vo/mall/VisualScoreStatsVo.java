package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.time.LocalDateTime;

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

    /**
     * 分数的主批次日期 —— 取「覆盖行数最多的那一天」，不是 max(update_time)。
     * 分数由批量脚本一次性写入，表里没有单独的"评分时间"列，行更新时间是唯一线索；
     * 但零星重算（单张 rescore / 补跑新图）会把 max() 推到今天，于是 15,242 张旧分数
     * 会被一行"数据截至今天"盖掉 —— 那和"停在旧批次不显示"是同一类撒谎，方向相反。
     */
    private LocalDateTime scoredAt;

    /** 主批次那天写了多少张 */
    private Integer scoredBatchRows;

    /** 比主批次更晚重算过的张数（界面要显出来，别让主批次看起来像全量） */
    private Integer scoredNewerRows;

    /** scoredAt（主批次）距今多少天，整天取整；从没评过分时为 null */
    private Integer staleDays;
}
