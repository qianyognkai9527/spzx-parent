package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.promo.PromoCostDaily;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PromoCostDailyMapper extends BaseMapper<PromoCostDaily> {

    /**
     * 按自然键 (shop_id, plan_type, campaign_id, stat_date) upsert。
     * 重导一份修正过的报表是常态，所以"重复导入 = 用新值覆盖"，而不是报错也不是堆重复行。
     * 用 MySQL 8.0.19+ 的行别名语法，不用已废弃的 VALUES() 函数。
     */
    @Insert("<script>INSERT INTO promo_cost_daily "
            + "(shop_id, platform_code, stat_date, plan_type, campaign_id, campaign_name, report_source, "
            + " charge, ad_pv, click, ctr_percent, cpc, cpm, gmv_total, gmv_direct, gmv_indirect, "
            + " order_total, order_direct, roi, cart_count, item_collect, shop_collect, chat_count, "
            + " raw_json, import_batch) VALUES "
            + "<foreach collection='rows' item='r' separator=','>"
            + "(#{r.shopId},#{r.platformCode},#{r.statDate},#{r.planType},#{r.campaignId},#{r.campaignName},#{r.reportSource},"
            + " #{r.charge},#{r.adPv},#{r.click},#{r.ctrPercent},#{r.cpc},#{r.cpm},#{r.gmvTotal},#{r.gmvDirect},#{r.gmvIndirect},"
            + " #{r.orderTotal},#{r.orderDirect},#{r.roi},#{r.cartCount},#{r.itemCollect},#{r.shopCollect},#{r.chatCount},"
            + " #{r.rawJson},#{r.importBatch})"
            + "</foreach> AS new "
            + "ON DUPLICATE KEY UPDATE "
            + " platform_code=new.platform_code, campaign_name=new.campaign_name, report_source=new.report_source,"
            + " charge=new.charge, ad_pv=new.ad_pv, click=new.click, ctr_percent=new.ctr_percent, cpc=new.cpc, cpm=new.cpm,"
            + " gmv_total=new.gmv_total, gmv_direct=new.gmv_direct, gmv_indirect=new.gmv_indirect,"
            + " order_total=new.order_total, order_direct=new.order_direct, roi=new.roi,"
            + " cart_count=new.cart_count, item_collect=new.item_collect, shop_collect=new.shop_collect, chat_count=new.chat_count,"
            + " raw_json=new.raw_json, import_batch=new.import_batch</script>")
    int upsertBatch(@Param("rows") List<PromoCostDaily> rows);
}
