package com.joker.spzx.manager.service.videogen;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Task 4 补充：parsePromptJson 截断与 storyboard 可选两条失败/边界路径测试。
 * 逻辑已含在 Task 2 的 VideoJsonUtil 实现中，预期直接通过（若失败回改 parsePromptJson）。
 */
class VideoPromptParseTest {

    @Test
    void promptTruncatedTo2000() {
        String big = "字".repeat(2500);
        var r = VideoJsonUtil.parsePromptJson("{\"prompt\":\"" + big + "\"}");
        assertEquals(2000, r.prompt().length());
    }

    @Test
    void storyboardOptional() {
        var r = VideoJsonUtil.parsePromptJson("{\"prompt\":\"p\"}");
        assertTrue(r.storyboard().isEmpty());
    }
}
