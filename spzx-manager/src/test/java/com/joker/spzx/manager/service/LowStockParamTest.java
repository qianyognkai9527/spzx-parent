package com.joker.spzx.manager.service;

import org.junit.jupiter.api.Test;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 低库存规格页参数白名单（纯 JUnit，不拉 Spring 上下文） */
class LowStockParamTest {

    @Test
    void 阈值白名单三档原样通过() {
        assertEquals(10, LowStockService.normalizeThreshold("10"));
        assertEquals(20, LowStockService.normalizeThreshold("20"));
        assertEquals(50, LowStockService.normalizeThreshold("50"));
    }

    @Test
    void 缺省与空白用默认20() {
        assertEquals(20, LowStockService.normalizeThreshold(null));
        assertEquals(20, LowStockService.normalizeThreshold(""));
        assertEquals(20, LowStockService.normalizeThreshold("  "));
        assertEquals(20, LowStockService.normalizeThreshold(" 20 "));
    }

    @Test
    void 白名单外回null由controller转400() {
        // spec 定死三档，多传一个 15 不该静默放行去查库
        assertNull(LowStockService.normalizeThreshold("15"));
        assertNull(LowStockService.normalizeThreshold("0"));
        assertNull(LowStockService.normalizeThreshold("-10"));
        assertNull(LowStockService.normalizeThreshold("abc"));
    }

    @Test
    void 分页参数缺省与夹取() {
        assertEquals(1, LowStockService.normalizeInt(null, 1, 1, 100000));
        assertEquals(20, LowStockService.normalizeInt(null, 20, 1, 100));
        assertEquals(1, LowStockService.normalizeInt(0, 20, 1, 100));
        assertEquals(100, LowStockService.normalizeInt(500, 20, 1, 100));
        assertEquals(7, LowStockService.normalizeInt(7, 20, 1, 100));
    }

    /** 从 classpath 读 mapper XML 原文（MyBatis 解析前的文本，含注释） */
    private static String mapperXml() {
        try (InputStream in = LowStockParamTest.class.getClassLoader()
                .getResourceAsStream("mapper/LowStockMapper.xml")) {
            assertNotNull(in, "mapper/LowStockMapper.xml 不在测试 classpath 上，一致性核对无从进行");
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    /** 主查询是否带「只显示铺货货源」过滤（EXISTS taobao_offer_map，用户口径 2026-10-17） */
    private static boolean hasDistributedFilter(String xml) {
        return Pattern.compile(
                "EXISTS\\s*\\(\\s*SELECT 1 FROM taobao_offer_map\\s+tm\\s+WHERE\\s+tm\\.source_product_id\\s*=\\s*sp\\.id",
                Pattern.CASE_INSENSITIVE).matcher(xml).find();
    }

    @Test
    void 主查询必须带铺货过滤_未铺货的货源不准混进页面() {
        // 用户口径（2026-10-17）：页面只显示淘宝铺货商品对应的1688货源；
        // 这条口径在 XML 里，编译器管不到，像 ItemOpsParamTest 一样逐字钉住原文
        assertTrue(hasDistributedFilter(mapperXml()),
                "selectLowStockGroups 缺少 taobao_offer_map 的铺货过滤（EXISTS），未铺货的选品货源会混进页面");
        // 自证抽取本身有效：一段没有该过滤的文本必须判负，而不是永远绿
        assertFalse(hasDistributedFilter(
                "<select id=\"selectLowStockGroups\">FROM source_sku sku JOIN source_product sp</select>"));
    }

    @Test
    void 处理类型只认下架删除和下架SKU() {
        assertEquals(1, LowStockService.normalizeHandleType(1));
        assertEquals(2, LowStockService.normalizeHandleType(2));
        assertEquals(3, LowStockService.normalizeHandleType(3));
        // 0/4/null/越界都不准落库——这是人工留痕字段，写进脏值比不写更糟
        assertNull(LowStockService.normalizeHandleType(null));
        assertNull(LowStockService.normalizeHandleType(0));
        assertNull(LowStockService.normalizeHandleType(4));
        assertNull(LowStockService.normalizeHandleType(-1));
    }

    @Test
    void 处理状态筛选仿facet白名单_非法回all() {
        // 筛选不是数据，非法值退回 all（同 ItemOpsService.normalizeFacet），不 400
        assertEquals("all", LowStockService.normalizeHandleFilter(null));
        assertEquals("all", LowStockService.normalizeHandleFilter(""));
        assertEquals("all", LowStockService.normalizeHandleFilter("  "));
        assertEquals("all", LowStockService.normalizeHandleFilter("enjoy"));
        assertEquals("all", LowStockService.normalizeHandleFilter("Pending")); // 大小写敏感，防踩进意外分支
        assertEquals("pending", LowStockService.normalizeHandleFilter(" pending "));
        assertEquals("done", LowStockService.normalizeHandleFilter("done"));
    }

    @Test
    void 主查询必须左联处理标记表() {
        // 标记在 low_stock_handle，主查询不 LEFT JOIN 的话标记列永远空白
        String xml = mapperXml();
        assertTrue(Pattern.compile("LEFT JOIN low_stock_handle h ON h\\.source_product_id\\s*=\\s*sp\\.id",
                Pattern.CASE_INSENSITIVE).matcher(xml).find(),
                "selectLowStockGroups 缺少 low_stock_handle 的 LEFT JOIN，处理标记不会显示");
        assertFalse(Pattern.compile("LEFT JOIN low_stock_handle h ON h\\.source_product_id\\s*=\\s*sp\\.id",
                Pattern.CASE_INSENSITIVE).matcher(
                "<select>FROM source_sku sku JOIN source_product sp</select>").find(),
                "自证失败：没有 JOIN 的文本也判真，抽取无效");
    }

    @Test
    void 失效筛选仿facet白名单_非法回no() {
        assertEquals("no", LowStockService.normalizeDeadFilter(null));
        assertEquals("no", LowStockService.normalizeDeadFilter(""));
        assertEquals("no", LowStockService.normalizeDeadFilter("enjoy"));
        assertEquals("dead", LowStockService.normalizeDeadFilter("dead"));
        assertEquals("no", LowStockService.normalizeDeadFilter("Dead")); // 大小写敏感
        assertEquals("dead", LowStockService.normalizeDeadFilter(" dead "));
    }

    @Test
    void 失效分组查询必须钉住source_status和铺货过滤() {
        String xml = mapperXml();
        assertTrue(Pattern.compile(
                "<select id=\"selectDeadGroups\"[\\s\\S]*?sp\\.source_status\\s*=\\s*0[\\s\\S]*?EXISTS[\\s\\S]*?taobao_offer_map",
                Pattern.CASE_INSENSITIVE).matcher(xml).find(),
                "selectDeadGroups 必须只查 source_status=0 且带铺货 EXISTS，否则失效页混入健康/未铺货货源");
        assertTrue(Pattern.compile(
                "sp\\.source_status\\s+AS\\s+sourceStatus", Pattern.CASE_INSENSITIVE).matcher(xml).find(),
                "主查询必须带出 sourceStatus 供前端失效徽标");
    }
}
