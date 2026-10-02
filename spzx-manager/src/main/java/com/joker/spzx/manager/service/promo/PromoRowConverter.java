package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.entity.promo.PromoCostDaily;
import com.joker.spzx.model.entity.promo.PromoCostItemDaily;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * 归一化后的字符串行 → 事实表实体。逐字段转换，单个字段坏掉只记这一行的错，不让整批导入回滚。
 *
 * 每列都按 DDL 的精度收窄：超上限的行报错跳过，避免 MySQL 在严格模式下整条语句失败。
 */
public final class PromoRowConverter {

    private static final BigDecimal MONEY_MAX = new BigDecimal("9999999999.99");
    private static final BigDecimal RATE_MAX = new BigDecimal("999999.9999");
    private static final long COUNT_MAX = 9_999_999_999L;

    private PromoRowConverter() {
    }

    /** 一行转换的产出：要么拿到实体，要么拿到错误列表 */
    public static class Converted<T> {
        public T entity;
        public final List<String> errors = new java.util.ArrayList<>();

        public boolean ok() {
            return errors.isEmpty() && entity != null;
        }
    }

    public static Converted<PromoCostDaily> toCampaign(Map<String, String> values, int lineNo,
                                                       Long shopId, Integer platformCode,
                                                       String planType, String reportSource,
                                                       String batch, String rawJson) {
        Converted<PromoCostDaily> out = new Converted<>();
        LocalDate date = PromoReportCsvParser.toDate(values.get("stat_date"));
        if (date == null) {
            out.errors.add("第" + lineNo + "行：日期缺失或格式不认识（值=" + values.get("stat_date") + "）");
            return out;
        }
        String campaignId = trim(values.get("campaign_id"));
        if (campaignId == null) {
            out.errors.add("第" + lineNo + "行：计划ID为空，无法去重");
            return out;
        }
        String chargeErr = checkMoney(values.get("charge"), "花费", lineNo, out.errors);
        if (chargeErr != null) {
            return out;
        }

        PromoCostDaily e = new PromoCostDaily();
        e.setShopId(shopId == null ? 0L : shopId);
        e.setPlatformCode(platformCode == null ? 1 : platformCode);
        e.setStatDate(date);
        e.setPlanType(planType);
        e.setCampaignId(campaignId);
        e.setCampaignName(trim(values.get("campaign_name")));
        e.setReportSource(reportSource == null ? "" : reportSource);
        e.setCharge(money(values.get("charge")));
        e.setAdPv(count(values.get("ad_pv")));
        e.setClick(count(values.get("click")));
        e.setCtrPercent(rate(values.get("ctr_percent")));
        e.setCpc(rate(values.get("cpc")));
        e.setCpm(rate(values.get("cpm")));
        e.setGmvTotal(money(values.get("gmv_total")));
        e.setGmvDirect(money(values.get("gmv_direct")));
        e.setGmvIndirect(money(values.get("gmv_indirect")));
        e.setOrderTotal(intOf(count(values.get("order_total"))));
        e.setOrderDirect(intOf(count(values.get("order_direct"))));
        e.setOrderIndirect(intOf(count(values.get("order_indirect"))));
        e.setRoi(money(values.get("roi")));
        e.setCvrPercent(rate(values.get("cvr_percent")));
        e.setOrderCost(rate(values.get("order_cost")));
        e.setCartCount(intOf(count(values.get("cart_count"))));
        e.setCartDirect(intOf(count(values.get("cart_direct"))));
        e.setCartIndirect(intOf(count(values.get("cart_indirect"))));
        e.setCartRatePercent(rate(values.get("cart_rate_percent")));
        e.setCartCost(rate(values.get("cart_cost")));
        e.setItemCollect(intOf(count(values.get("item_collect"))));
        e.setShopCollect(intOf(count(values.get("shop_collect"))));
        e.setCollectTotal(intOf(count(values.get("collect_total"))));
        e.setItemCollectRatePercent(rate(values.get("item_collect_rate_percent")));
        e.setItemCollectCost(rate(values.get("item_collect_cost")));
        e.setShopCollectCost(rate(values.get("shop_collect_cost")));
        e.setCollectCartTotal(intOf(count(values.get("collect_cart_total"))));
        e.setCollectCartCost(rate(values.get("collect_cart_cost")));
        e.setItemCollectCart(intOf(count(values.get("item_collect_cart"))));
        e.setItemCollectCartCost(rate(values.get("item_collect_cart_cost")));
        e.setShoppingAmt(money(values.get("shopping_amt")));
        e.setAddNewUv(intOf(count(values.get("add_new_uv"))));
        e.setBidType(trim(values.get("bid_type")));
        e.setRawJson(rawJson);
        e.setImportBatch(batch);
        out.entity = e;
        return out;
    }

    public static Converted<PromoCostItemDaily> toItem(Map<String, String> values, int lineNo,
                                                       Long shopId, Integer platformCode,
                                                       String planType, String reportSource,
                                                       String batch, String rawJson) {
        Converted<PromoCostItemDaily> out = new Converted<>();
        LocalDate date = PromoReportCsvParser.toDate(values.get("stat_date"));
        if (date == null) {
            out.errors.add("第" + lineNo + "行：日期缺失或格式不认识（值=" + values.get("stat_date") + "）");
            return out;
        }
        String entityKey = PromoReportCsvParser.entityKeyOf(values);
        if (entityKey == null) {
            out.errors.add("第" + lineNo + "行：明细标识为空（关键词/人群/宝贝名或 id 都没值）");
            return out;
        }
        String chargeErr = checkMoney(values.get("charge"), "花费", lineNo, out.errors);
        if (chargeErr != null) {
            return out;
        }

        PromoCostItemDaily e = new PromoCostItemDaily();
        e.setShopId(shopId == null ? 0L : shopId);
        e.setPlatformCode(platformCode == null ? 1 : platformCode);
        e.setStatDate(date);
        e.setPlanType(planType);
        e.setDimension(PromoReportCsvParser.dimensionOf(values));
        e.setEntityKey(entityKey);
        e.setEntityId(trim(values.get("entity_id")));
        e.setEntityName(PromoReportCsvParser.entityNameOf(values));
        // 唯一键包含 campaign_id，NULL 之间不算重复，重导会堆重复行 → 留空串
        e.setItemId(trim(values.get("item_id")));
        e.setItemName(trim(values.get("item_name")));
        e.setCampaignId(orEmpty(trim(values.get("campaign_id"))));
        e.setCampaignName(trim(values.get("campaign_name")));
        e.setUnitId(trim(values.get("unit_id")));
        e.setUnitName(trim(values.get("unit_name")));
        e.setReportSource(reportSource == null ? "" : reportSource);
        e.setCharge(money(values.get("charge")));
        e.setAdPv(count(values.get("ad_pv")));
        e.setClick(count(values.get("click")));
        e.setCtrPercent(rate(values.get("ctr_percent")));
        e.setCpc(rate(values.get("cpc")));
        e.setCpm(rate(values.get("cpm")));
        e.setGmvTotal(money(values.get("gmv_total")));
        e.setGmvDirect(money(values.get("gmv_direct")));
        e.setGmvIndirect(money(values.get("gmv_indirect")));
        e.setOrderTotal(intOf(count(values.get("order_total"))));
        e.setOrderDirect(intOf(count(values.get("order_direct"))));
        e.setOrderIndirect(intOf(count(values.get("order_indirect"))));
        e.setRoi(money(values.get("roi")));
        e.setCvrPercent(rate(values.get("cvr_percent")));
        e.setOrderCost(rate(values.get("order_cost")));
        e.setCartCount(intOf(count(values.get("cart_count"))));
        e.setCartDirect(intOf(count(values.get("cart_direct"))));
        e.setCartIndirect(intOf(count(values.get("cart_indirect"))));
        e.setCartRatePercent(rate(values.get("cart_rate_percent")));
        e.setCartCost(rate(values.get("cart_cost")));
        e.setItemCollect(intOf(count(values.get("item_collect"))));
        e.setShopCollect(intOf(count(values.get("shop_collect"))));
        e.setCollectTotal(intOf(count(values.get("collect_total"))));
        e.setItemCollectRatePercent(rate(values.get("item_collect_rate_percent")));
        e.setItemCollectCost(rate(values.get("item_collect_cost")));
        e.setShopCollectCost(rate(values.get("shop_collect_cost")));
        e.setCollectCartTotal(intOf(count(values.get("collect_cart_total"))));
        e.setCollectCartCost(rate(values.get("collect_cart_cost")));
        e.setItemCollectCart(intOf(count(values.get("item_collect_cart"))));
        e.setItemCollectCartCost(rate(values.get("item_collect_cart_cost")));
        e.setShoppingAmt(money(values.get("shopping_amt")));
        e.setAddNewUv(intOf(count(values.get("add_new_uv"))));
        e.setRawJson(rawJson);
        e.setImportBatch(batch);
        out.entity = e;
        return out;
    }

    /** 返回 null 表示这行可以继续；非 null 是错误文案（已同时追加进 errors） */
    private static String checkMoney(String raw, String label, int lineNo, List<String> errors) {
        String v = PromoReportCsvParser.emptyToNull(raw);
        if (v == null) {
            return null;
        }
        BigDecimal d = PromoReportCsvParser.toDecimal(v);
        if (d == null) {
            errors.add("第" + lineNo + "行：" + label + "不是数字（值=" + v + "）");
            return label;
        }
        if (d.compareTo(MONEY_MAX) > 0) {
            errors.add("第" + lineNo + "行：" + label + "超出可导入上限 " + MONEY_MAX.toPlainString() + "（值=" + v + "）");
            return label;
        }
        return null;
    }

    private static BigDecimal money(String raw) {
        BigDecimal d = PromoReportCsvParser.toDecimal(raw);
        return d == null ? null : d.setScale(2, RoundingMode.HALF_UP);
    }

    private static BigDecimal rate(String raw) {
        BigDecimal d = PromoReportCsvParser.toDecimal(raw);
        if (d == null) {
            return null;
        }
        if (d.abs().compareTo(RATE_MAX) > 0) {
            return null;
        }
        return d.setScale(4, RoundingMode.HALF_UP);
    }

    private static Long count(String raw) {
        Long v = PromoReportCsvParser.toLong(raw);
        if (v == null || Math.abs(v) > COUNT_MAX) {
            return null;
        }
        return v;
    }

    private static Integer intOf(Long v) {
        if (v == null) {
            return null;
        }
        return v > Integer.MAX_VALUE ? Integer.MAX_VALUE : (int) v.longValue();
    }

    private static String orEmpty(String s) {
        return s == null ? "" : s;
    }

    private static String trim(String s) {
        String v = PromoReportCsvParser.emptyToNull(s);
        return v == null ? null : v.trim();
    }
}
