package com.joker.spzx.manager.service.impl;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 主图质量分的"截至"天数 —— 纯函数，不拉 Spring。
 *
 * 守的是这页唯一的谎：分数由批量脚本一次性写死（库里 18611 个分数最后写入 2026-08-21），
 * 界面却不提时间，让人拿 43 天前的评级当实时结论用。
 */
class VisualScoreStalenessTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 10, 3);

    @Test
    void 按整天算出距今年数() {
        // 库里真实值：2026-08-21 20:16:49 是最后一批写分时间
        assertEquals(43, VisualScoreServiceImpl.staleDays(
                LocalDateTime.of(2026, 8, 21, 20, 16, 49), TODAY));
    }

    @Test
    void 从没评过分是_null_而不是_0_天() {
        // 0 天会被读成"今天刚跑过"，那是另一种假
        assertNull(VisualScoreServiceImpl.staleDays(null, TODAY));
    }

    @Test
    void 当天算零天而不是按小时() {
        assertEquals(0, VisualScoreServiceImpl.staleDays(
                LocalDateTime.of(2026, 10, 3, 0, 5, 0), TODAY));
        assertEquals(0, VisualScoreServiceImpl.staleDays(
                LocalDateTime.of(2026, 10, 3, 23, 59, 0), TODAY));
    }

    @Test
    void 未来时间不给出负数() {
        // 机器时钟偏差或库里脏数据时，"距今 -2 天"比不显示更糟
        assertEquals(0, VisualScoreServiceImpl.staleDays(
                LocalDateTime.of(2026, 10, 5, 9, 0, 0), TODAY));
    }
}
