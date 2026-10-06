package com.joker.spzx.manager.service;

import com.joker.spzx.manager.mapper.DashboardMapper;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.Set;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ItemOpsParamTest {

    @Test
    void 白名单内的筛选项原样通过() {
        for (String facet : new String[]{"all", "noSale", "negativeMargin", "lowStock", "noEffect",
                "noSource", "unpriced", "abnormalTraffic"}) {
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

    /** 从 classpath 读 mapper XML 原文（MyBatis 解析前的文本，含注释） */
    private static String mapperXml() {
        try (InputStream in = ItemOpsParamTest.class.getClassLoader()
                .getResourceAsStream("mapper/ItemOpsMapper.xml")) {
            assertNotNull(in, "mapper/ItemOpsMapper.xml 不在测试 classpath 上，一致性核对无从进行");
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** XML 里 {@code <when test="facet == 'x'">} 出现过的筛选项 */
    private static Set<String> facetsInXml(String xml) {
        Matcher m = Pattern.compile("facet == '(\\w+)'").matcher(xml);
        Set<String> out = new TreeSet<>();
        while (m.find()) {
            out.add(m.group(1));
        }
        return out;
    }

    @Test
    void 白名单与mapper里的筛选分支一一对应() {
        Set<String> inJava = new TreeSet<>(ItemOpsService.FACETS);
        inJava.remove("all");   // all 是 <otherwise>，不会以 facet == 'all' 出现
        Set<String> inXml = facetsInXml(mapperXml());
        assertEquals(inJava, inXml, "ItemOpsService.FACETS 与 ItemOpsMapper.xml 的筛选分支不一致");

        // 自证抽取本身有效，而不是两边都空所以相等：先拿一段已知文本喂它
        assertEquals(Set.of("noSale"), facetsInXml("<when test=\"facet == 'noSale'\">x</when>"));
        assertEquals(Set.of(), facetsInXml("<select id=\"pageItems\">没有筛选项</select>"));
        // 新加的分支必须真在文件里，删掉这条 when 就该在这里爆
        assertTrue(inXml.contains("abnormalTraffic"));
    }

    @Test
    void 每个筛选项都有同名角标计数() {
        String xml = mapperXml();
        for (String facet : facetsInXml(xml)) {
            assertTrue(Pattern.compile("AS " + facet + "\\b").matcher(xml).find(),
                    "筛选项 " + facet + " 在 selectFacetCounts 里没有同名别名，前端角标会缺一个");
        }
    }

    @Test
    void 首页与运营台的异常流量判据逐字一致() {
        String xml = mapperXml();
        Matcher m = Pattern.compile(
                "CASE WHEN (e\\.visitors.*?)THEN 1 ELSE 0 END\\s+AS abnormalTraffic", Pattern.DOTALL).matcher(xml);
        assertTrue(m.find(), "ItemOpsMapper.xml 里没找到 abnormalTraffic 判据，抽取本身失效了");
        String fromXml = normalize(m.group(1));
        // 抽取抓空/抓窄也会让"相等"看着成立，先确认抓到的是判据本体
        assertTrue(fromXml.contains("COALESCE"), "抽取到的片段不像一条判据: " + fromXml);
        assertEquals(normalize(DashboardMapper.ABNORMAL_TRAFFIC), fromXml,
                "两页按不同口径剔流量，同一个商品会在首页趋势和运营台给出矛盾结论");
    }

    /** 去掉 join 别名前缀、XML 实体和多余空白，只留判据本体。
     *  括号要保留 —— 它们是 SQL 语义的一部分，抹平了就漏掉了 AND/OR 优先级被改坏这种情况。 */
    private static String normalize(String s) {
        return s.replace("e.", "").replace("&gt;", ">").replace("&lt;", "<")
                .replaceAll("\\s+", " ").trim();
    }
}
