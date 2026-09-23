package com.joker.spzx.manager.service.videogen;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class VideoJsonUtilTest {

    @Test
    void extractsFencedJson() {
        assertEquals("{\"prompt\":\"a\"}",
                VideoJsonUtil.extractJsonObject("```json\n{\"prompt\":\"a\"}\n```"));
    }

    @Test
    void extractsEmbedded() {
        assertEquals("{\"a\":1}", VideoJsonUtil.extractJsonObject("废话 {\"a\":1} 废话"));
    }

    @Test
    void nullWhenNoBrace() {
        assertNull(VideoJsonUtil.extractJsonObject("没有json"));
    }

    @Test
    void parsesPrompt() {
        var r = VideoJsonUtil.parsePromptJson("{\"storyboard\":[{\"shot\":1,\"desc\":\"x\"}],\"prompt\":\"主体描述\"}");
        assertEquals("主体描述", r.prompt());
        assertEquals(1, r.storyboard().size());
    }

    @Test
    void missingPromptThrows() {
        assertThrows(IllegalArgumentException.class,
                () -> VideoJsonUtil.parsePromptJson("{\"storyboard\":[]}"));
    }
}
