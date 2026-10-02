package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.entity.promo.PromoCostDaily;
import com.joker.spzx.model.entity.promo.PromoCostItemDaily;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PromoReportCsvParserTest {

    /** BigDecimal.equals 连 scale 一起比；归一化只关心数值，scale 由目标列负责 */
    private static void assertDecimal(String expected, BigDecimal actual) {
        assertNotNull(actual, "应当解析出数值");
        assertTrue(actual.compareTo(new BigDecimal(expected)) == 0,
                () -> expected + " != " + actual);
    }

    private static Map<String, String> campaignMap() {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("日期", "stat_date");
        m.put("计划ID", "campaign_id");
        m.put("计划名称", "campaign_name");
        m.put("花费", "charge");
        m.put("展现量", "ad_pv");
        m.put("点击量", "click");
        m.put("点击率", "ctr_percent");
        m.put("总成交金额", "gmv_total");
        m.put("投入产出比", "roi");
        return m;
    }

    private static List<List<String>> records(String... lines) {
        return com.joker.spzx.manager.util.CsvText.splitRecords(String.join("\n", lines));
    }

    private static PromoReportCsvParser.Result parseCampaign(List<List<String>> recs) {
        return new PromoReportCsvParser().parseRecords(recs, campaignMap(), "campaign");
    }

    // ==================== 值归一化 ====================

    @Test
    void 各种空值写法都算空() {
        for (String s : new String[]{null, "", "   ", "-", "--", "/", "－", "null", "NULL", "暂无", "N/A", "na"}) {
            assertNull(PromoReportCsvParser.emptyToNull(s), "应当作空: " + s);
        }
        assertEquals("0", PromoReportCsvParser.emptyToNull(" 0 "));
    }

    @Test
    void 金额去掉货币符号与千分位() {
        assertDecimal("1234.56", PromoReportCsvParser.toDecimal("¥1,234.56"));
        assertDecimal("1234.56", PromoReportCsvParser.toDecimal("￥1,234.56元"));
        assertDecimal("123456", PromoReportCsvParser.toDecimal("12.3456万"));
        assertDecimal("300000000", PromoReportCsvParser.toDecimal("3亿"));
        assertDecimal("-45.9", PromoReportCsvParser.toDecimal("-45.90"));
    }

    @Test
    void 百分号去掉但数值保持百分数原样() {
        // ctr_percent 存的就是"12.34"这种百分数，不在导入阶段猜它是不是小数
        assertDecimal("12.34", PromoReportCsvParser.toDecimal("12.34%"));
        assertDecimal("0.5", PromoReportCsvParser.toDecimal("0.50%"));
    }

    @Test
    void 非数字返回null而不是抛异常() {
        assertNull(PromoReportCsvParser.toDecimal("abc"));
        assertNull(PromoReportCsvParser.toDecimal(""));
        assertNull(PromoReportCsvParser.toDecimal("--"));
        assertNull(PromoReportCsvParser.toLong("点击"));
    }

    @Test
    void 计数四舍五入到整数() {
        assertEquals(1235L, PromoReportCsvParser.toLong("1,234.6"));
        assertEquals(0L, PromoReportCsvParser.toLong("0"));
        assertEquals(12345L, PromoReportCsvParser.toLong("1.2345万"));
    }

    @Test
    void 日期支持多种导出写法() {
        LocalDate expect = LocalDate.of(2026, 9, 3);
        for (String raw : new String[]{"2026-09-03", "2026/9/3", "20260903", "2026.09.03",
                "2026-09-03 00:00:00", "2026年9月3日"}) {
            assertEquals(expect, PromoReportCsvParser.toDate(raw), "解析失败: " + raw);
        }
        assertNull(PromoReportCsvParser.toDate("最近7天"));
        assertNull(PromoReportCsvParser.toDate(""));
    }

    // ==================== 表头与列映射 ====================

    @Test
    void 表头前的标题块会被跳过() {
        PromoReportCsvParser.Result r = parseCampaign(records(
                "万相台无界版报表导出",
                "导出时间: 2026-09-30",
                "日期,计划ID,计划名称,花费",
                "2026-09-29,1001,关键词标准计划A,120.50"));
        assertEquals(3, r.headerLine);
        assertEquals(1, r.totalRows);
        assertEquals("2026-09-29", r.rows.get(0).values.get("stat_date"));
        assertEquals("1001", r.rows.get(0).values.get("campaign_id"));
    }

    @Test
    void 未映射的列原样报出来而不是丢掉() {
        PromoReportCsvParser.Result r = parseCampaign(records(
                "日期,计划ID,花费,总收藏加购数,平均展现排名",
                "2026-09-29,1001,120.50,7,3.2"));
        assertEquals(List.of("总收藏加购数", "平均展现排名"), r.unmapped);
        assertTrue(r.matched.containsKey("花费"));
    }

    @Test
    void 映射指向本层不认识的字段要报出来() {
        Map<String, String> m = campaignMap();
        m.put("人群名称", "entity_name");   // entity_* 只在 item 层有效
        PromoReportCsvParser.Result r = new PromoReportCsvParser()
                .parseRecords(records("日期,计划ID,花费,人群名称", "2026-09-29,1001,1,女"), m, "campaign");
        assertEquals(List.of("人群名称 → entity_name"), r.unknownTargets);
        assertFalse(r.matched.containsKey("人群名称"));
    }

    @Test
    void 缺必需列时报出缺哪一列() {
        PromoReportCsvParser.Result r = new PromoReportCsvParser().parseRecords(
                records("日期,计划名称,花费", "2026-09-29,A,1"),
                Map.of("日期", "stat_date", "计划名称", "campaign_name", "花费", "charge"), "campaign");
        // 解析器照样出行，是服务层拿 missingRequired 短路拒绝导入的（见 PromoCostService#importCsv）
        assertEquals(List.of("campaign_id"), r.missingRequired);
    }

    @Test
    void 一列都对不上时不假装解析成功() {
        PromoReportCsvParser.Result r = parseCampaign(records("a,b,c", "1,2,3"));
        assertTrue(r.headers.isEmpty());
        assertFalse(r.errors.isEmpty());
    }

    @Test
    void 空行与全空值行不计入数据行() {
        PromoReportCsvParser.Result r = parseCampaign(records(
                "日期,计划ID,花费",
                "2026-09-29,1001,1",
                "",
                ",,",
                "2026-09-28,,2"));
        // 第三行计划ID为空但仍会被解析出来，由转换器负责报错；第四行是空行
        assertEquals(2, r.rows.size());
        assertEquals(2, r.blankRows);
    }

    // ==================== 明细维度推导 ====================

    @Test
    void 关键词列决定dimension与entityKey() {
        Map<String, String> values = new LinkedHashMap<>();
        values.put("entity_keyword", "连衣裙 夏季");
        assertEquals("keyword", PromoReportCsvParser.dimensionOf(values));
        assertEquals("连衣裙 夏季", PromoReportCsvParser.entityKeyOf(values));
        assertEquals("连衣裙 夏季", PromoReportCsvParser.entityNameOf(values));
    }

    @Test
    void 有id时用id当entityKey() {
        Map<String, String> values = new LinkedHashMap<>();
        values.put("entity_item", "某商品标题");
        values.put("entity_id", "935918678330");
        assertEquals("item", PromoReportCsvParser.dimensionOf(values));
        assertEquals("935918678330", PromoReportCsvParser.entityKeyOf(values));
        assertEquals("某商品标题", PromoReportCsvParser.entityNameOf(values));
    }

    @Test
    void 没有任何实体列时dimension为other且key为空() {
        Map<String, String> values = new LinkedHashMap<>();
        values.put("campaign_id", "1001");
        assertEquals("other", PromoReportCsvParser.dimensionOf(values));
        assertNull(PromoReportCsvParser.entityKeyOf(values));
    }

    // ==================== 行转换 ====================

    @Test
    void 计划行正常转换并按精度收窄() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026/9/29");
        v.put("campaign_id", "1001");
        v.put("campaign_name", "关键词标准计划A");
        v.put("charge", "¥1,234.567");
        v.put("ad_pv", "56,789");
        v.put("click", "1,234.6");
        v.put("ctr_percent", "2.17%");
        v.put("gmv_total", "8888.8");
        v.put("roi", "7.2");

        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 4, null, null, "keyword", "file.csv", "b1", "{}");
        assertTrue(c.errors.isEmpty(), () -> c.errors.toString());
        PromoCostDaily e = c.entity;
        assertEquals(LocalDate.of(2026, 9, 29), e.getStatDate());
        assertEquals(0L, e.getShopId());          // 未指定店铺落成 0，不能是 NULL
        assertEquals(1, e.getPlatformCode());
        assertEquals("keyword", e.getPlanType());
        assertEquals(new BigDecimal("1234.57"), e.getCharge());
        assertEquals(56789L, e.getAdPv());
        assertEquals(1235L, e.getClick());
        assertEquals(new BigDecimal("2.1700"), e.getCtrPercent());
        assertEquals(new BigDecimal("8888.80"), e.getGmvTotal());
        assertEquals("file.csv", e.getReportSource());
    }

    @Test
    void 报表没给的列保持null而不是0() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("campaign_id", "1001");
        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 5, 2L, 1, "crowd", "", "b1", null);
        assertTrue(c.errors.isEmpty());
        assertNull(c.entity.getCharge());
        assertNull(c.entity.getGmvTotal());
        assertNull(c.entity.getRoi());
        assertEquals(2L, c.entity.getShopId());
    }

    @Test
    void 日期解析不了只报错这一行() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "最近7天");
        v.put("campaign_id", "1001");
        v.put("charge", "10");
        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 7, null, null, "keyword", "", "b1", null);
        assertNull(c.entity);
        assertEquals(1, c.errors.size());
        assertTrue(c.errors.get(0).contains("第7行"));
        assertTrue(c.errors.get(0).contains("日期"));
    }

    @Test
    void 计划ID为空无法去重时报错() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("campaign_id", "-");
        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 8, null, null, "keyword", "", "b1", null);
        assertNull(c.entity);
        assertTrue(c.errors.get(0).contains("计划ID"));
    }

    @Test
    void 花费超出金额上限时报错而不是让整条语句失败() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("campaign_id", "1001");
        v.put("charge", "99999999999999");
        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 9, null, null, "keyword", "", "b1", null);
        assertNull(c.entity);
        assertTrue(c.errors.get(0).contains("超出可导入上限"));
    }

    @Test
    void 花费不是数字时报错并带上原值() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("campaign_id", "1001");
        v.put("charge", "待结算");
        PromoRowConverter.Converted<PromoCostDaily> c =
                PromoRowConverter.toCampaign(v, 10, null, null, "keyword", "", "b1", null);
        assertNull(c.entity);
        assertTrue(c.errors.get(0).contains("待结算"));
    }

    @Test
    void 明细行缺实体标识时报错() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("charge", "12");
        PromoRowConverter.Converted<PromoCostItemDaily> c =
                PromoRowConverter.toItem(v, 11, null, null, "keyword", "", "b1", null);
        assertNull(c.entity);
        assertTrue(c.errors.get(0).contains("明细标识"));
    }

    @Test
    void 明细行campaignId留空串而不是null() {
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-29");
        v.put("entity_keyword", "连衣裙");
        v.put("charge", "12.3");
        PromoRowConverter.Converted<PromoCostItemDaily> c =
                PromoRowConverter.toItem(v, 12, null, null, "keyword", "", "b1", null);
        assertTrue(c.errors.isEmpty(), () -> c.errors.toString());
        assertEquals("keyword", c.entity.getDimension());
        assertEquals("连衣裙", c.entity.getEntityKey());
        assertEquals("", c.entity.getCampaignId());   // 唯一键里的列留空串，不留 NULL
        assertEquals(new BigDecimal("12.30"), c.entity.getCharge());
    }

    @Test
    void 关键词行同时带宝贝id时两者各归各位() {
        // 真实报表里一行 = (关键词, 该词投在哪个宝贝)。合成一个 entity 字段会要么丢关键词、
        // 要么 dimension 认不出来，所以 item_id 与 entity_* 必须分开
        Map<String, String> v = new LinkedHashMap<>();
        v.put("stat_date", "2026-09-28");
        v.put("entity_keyword", "连衣裙 夏季");
        v.put("item_id", "935918678330");
        v.put("item_name", "十三行美式牛仔短裤");
        v.put("charge", "320.50");
        PromoRowConverter.Converted<PromoCostItemDaily> c =
                PromoRowConverter.toItem(v, 20, 1L, 1, "keyword", "kw.csv", "b", null);
        assertTrue(c.errors.isEmpty(), () -> c.errors.toString());
        assertEquals("keyword", c.entity.getDimension());
        assertEquals("连衣裙 夏季", c.entity.getEntityKey());
        assertEquals("连衣裙 夏季", c.entity.getEntityName());
        assertEquals("935918678330", c.entity.getItemId());
        assertEquals("十三行美式牛仔短裤", c.entity.getItemName());
    }

    @Test
    void 目标字段白名单按层级分开() {
        java.util.Set<String> camp = PromoReportCsvParser.targetsOf("campaign");
        java.util.Set<String> item = PromoReportCsvParser.targetsOf("item");
        // 标识类字段必须分层：明细层才有 entity_*/item_id，计划层才有 bid_type
        assertTrue(item.contains("entity_keyword"));
        assertTrue(item.contains("item_id"));
        assertFalse(camp.contains("entity_keyword"));
        assertFalse(camp.contains("item_id"));
        assertTrue(camp.contains("bid_type"));
        assertFalse(item.contains("bid_type"));
        // 指标类字段两层是同一套：接口在单元(adgroup)层返回的是同一批字段名，
        // 明细表比计划表薄没有理由（2026-10-02 补齐 cpm/order_direct/shop_collect 等）
        for (String m : new String[]{"cpm", "shop_collect", "order_direct", "order_indirect", "add_new_uv"}) {
            assertTrue(camp.contains(m), "计划层缺指标 " + m);
            assertTrue(item.contains(m), "明细层缺指标 " + m);
        }
    }
}
