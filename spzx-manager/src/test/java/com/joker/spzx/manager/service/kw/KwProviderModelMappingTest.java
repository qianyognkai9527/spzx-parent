package com.joker.spzx.manager.service.kw;

import com.joker.spzx.model.entity.kw.KwProvider;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * kind → 模型列的映射已收口到 KwProviderService.modelOf（原先在 service 与 controller 里抄了 4 份 switch）。
 * 这组用例锁住的就是"新增 kind 只改一处"这件事：改坏映射会立刻在这里爆。
 */
class KwProviderModelMappingTest {

    private KwProvider fullRow() {
        KwProvider row = new KwProvider();
        row.setTextModel("text-x");
        row.setVisionModel("vision-y");
        row.setVideoModel("video-z");
        return row;
    }

    @Test
    void 三种kind各自命中对应模型列() {
        assertEquals("vision-y", KwProviderService.modelOf(fullRow(), "vision"));
        assertEquals("video-z", KwProviderService.modelOf(fullRow(), "video"));
        assertEquals("text-x", KwProviderService.modelOf(fullRow(), "text"));
    }

    @Test
    void 未登记的kind落到文本模型() {
        // default 分支是"其它一律 text"，新增 image 这类 kind 时若忘了加 case，行为仍是 text，
        // 由 requireActive 的"未配置 xx 模型"提示兜住，不会静默用错模型
        assertEquals("text-x", KwProviderService.modelOf(fullRow(), "image"));
    }

    @Test
    void 缺列返回null交给调用方判定() {
        KwProvider textOnly = new KwProvider();
        textOnly.setTextModel("text-x");
        assertNull(KwProviderService.modelOf(textOnly, "video"));
        assertNull(KwProviderService.modelOf(textOnly, "vision"));
    }

    @Test
    void 运行时定义与实体口径一致() {
        var def = new KwProviderService.ProviderDef("n", "http://u", "k",
                "vision-y", "text-x", "video-z", null, null, null);
        for (String kind : new String[]{"vision", "video", "text", "image"}) {
            assertEquals(KwProviderService.modelOf(fullRow(), kind), def.modelFor(kind),
                    "kind=" + kind + " 两条路径的映射不一致");
        }
    }
}
