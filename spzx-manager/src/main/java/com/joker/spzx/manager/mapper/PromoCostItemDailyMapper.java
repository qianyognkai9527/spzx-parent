package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.promo.PromoCostItemDaily;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PromoCostItemDailyMapper extends BaseMapper<PromoCostItemDaily> {

    /** 按 (shop_id, dimension, entity_key, campaign_id, stat_date) upsert；campaign_id 用空串而不是 NULL，见 DDL 注释 */
    @Insert("<script>INSERT INTO promo_cost_item_daily "
            + "(shop_id, platform_code, stat_date, plan_type, dimension, entity_key, entity_id, entity_name, item_id, item_name, "
            + " campaign_id, campaign_name, unit_id, unit_name, report_source, "
            + " charge, ad_pv, click, ctr_percent, cpc, gmv_total, gmv_direct, gmv_indirect, "
            + " order_total, roi, cart_count, item_collect, raw_json, import_batch) VALUES "
            + "<foreach collection='rows' item='r' separator=','>"
            + "(#{r.shopId},#{r.platformCode},#{r.statDate},#{r.planType},#{r.dimension},#{r.entityKey},#{r.entityId},#{r.entityName},#{r.itemId},#{r.itemName},"
            + " #{r.campaignId},#{r.campaignName},#{r.unitId},#{r.unitName},#{r.reportSource},"
            + " #{r.charge},#{r.adPv},#{r.click},#{r.ctrPercent},#{r.cpc},#{r.gmvTotal},#{r.gmvDirect},#{r.gmvIndirect},"
            + " #{r.orderTotal},#{r.roi},#{r.cartCount},#{r.itemCollect},#{r.rawJson},#{r.importBatch})"
            + "</foreach> AS new "
            + "ON DUPLICATE KEY UPDATE "
            + " platform_code=new.platform_code, plan_type=new.plan_type, entity_id=new.entity_id, entity_name=new.entity_name, item_id=new.item_id, item_name=new.item_name,"
            + " campaign_name=new.campaign_name, unit_id=new.unit_id, unit_name=new.unit_name, report_source=new.report_source,"
            + " charge=new.charge, ad_pv=new.ad_pv, click=new.click, ctr_percent=new.ctr_percent, cpc=new.cpc,"
            + " gmv_total=new.gmv_total, gmv_direct=new.gmv_direct, gmv_indirect=new.gmv_indirect,"
            + " order_total=new.order_total, roi=new.roi, cart_count=new.cart_count,"
            + " item_collect=new.item_collect,"
            + " raw_json=new.raw_json, import_batch=new.import_batch</script>")
    int upsertBatch(@Param("rows") List<PromoCostItemDaily> rows);
}
