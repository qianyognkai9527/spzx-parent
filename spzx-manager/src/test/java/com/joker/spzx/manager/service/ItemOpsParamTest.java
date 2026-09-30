package com.joker.spzx.manager.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ItemOpsParamTest {

    @Test
    void 白名单内的筛选项原样通过() {
        for (String facet : new String[]{"all", "noSale", "negativeMargin", "lowStock", "noEffect", "noSource", "unpriced"}) {
            assertEquals(facet, ItemOpsService.normalizeFacet(facet));
        }
    }

    @Test
    void 非法筛选项退回all而不是报错() {
        // 前端多传一个拼错的 facet 不该让整页空白
        assertEquals("all", ItemOpsService.normalizeFacet("enjoy"));
        assertEquals("all", ItemOpsService.normalizeFacet(""));
        assertEquals("all", ItemOpsService.normalizeFacet(null));
        assertEquals("noSale", ItemOpsService.normalizeFacet("  noSale  "));
        // 大小写敏感：SQL 分支按小写匹配，NoSale 必须退回 all 而不是走到意外分支
        assertEquals("all", ItemOpsService.normalizeFacet("NoSale"));
    }

    @Test
    void 阈值缺省与夹取() {
        assertEquals(10, ItemOpsService.normalizeInt(null, 10, 0, 1000));
        assertEquals(0, ItemOpsService.normalizeInt(-5, 10, 0, 1000));       // 夹到下限
        assertEquals(1000, ItemOpsService.normalizeInt(99999, 10, 0, 1000)); // 夹到上限
        assertEquals(0, ItemOpsService.normalizeInt(0, 10, 0, 1000));        // 0 是合法值不是缺省
    }
}
