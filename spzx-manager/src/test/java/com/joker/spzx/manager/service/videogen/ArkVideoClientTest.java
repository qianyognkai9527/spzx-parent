package com.joker.spzx.manager.service.videogen;

import cn.hutool.json.JSONUtil;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * ArkVideoClient 请求体构造纯函数测试（不联网）。
 * 断言严格对齐火山方舟 Seedance 视频生成 external 契约字段名/结构。
 */
class ArkVideoClientTest {

    @Test
    void buildBodyHasFirstFrame() {
        String body = new ArkVideoClient().buildSubmitBody(
                "m1", "一只猫", "data:image/jpeg;base64,QUJD", 5, "9:16");
        var obj = JSONUtil.parseObj(body);
        assertEquals("m1", obj.getStr("model"));
        var content = obj.getJSONArray("content");
        assertEquals("text", content.getJSONObject(0).getStr("type"));
        var img = content.getJSONObject(1);
        assertEquals("first_frame", img.getStr("role"));
        assertEquals("data:image/jpeg;base64,QUJD", img.getJSONObject("image_url").getStr("url"));
        assertEquals(5, obj.getInt("duration"));
        assertEquals("9:16", obj.getStr("ratio"));
        assertEquals(Boolean.FALSE, obj.getBool("generate_audio"));
    }
}
