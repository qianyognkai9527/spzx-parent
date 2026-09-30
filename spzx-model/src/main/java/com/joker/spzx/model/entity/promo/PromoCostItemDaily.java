package com.joker.spzx.model.entity.promo;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 付费推广明细粒度日报：关键词 / 人群 / 创意 / 宝贝 / 地域。
 *
 * dimension='item' 那一层是整套东西的目的：只有推广花费落到商品上，
 * 商品运营台的毛利才能扣掉推广费，算出真实 ROI。
 */
@Data
@Schema(name = "PromoCostItemDaily", description = "付费推广明细粒度日报")
@TableName("promo_cost_item_daily")
public class PromoCostItemDaily {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("shop_id")
    private Long shopId;

    @TableField("platform_code")
    private Integer platformCode;

    @TableField("stat_date")
    private LocalDate statDate;

    @Schema(description = "keyword|crowd|site|other（计划类型）")
    @TableField("plan_type")
    private String planType;

    @Schema(description = "明细维度：keyword|crowd|creative|item|region|unit")
    private String dimension;

    @Schema(description = "明细标识：有 id 用 id，没有则用名称（关键词本身没有 id）")
    @TableField("entity_key")
    private String entityKey;

    @TableField("entity_id")
    private String entityId;

    @Schema(description = "关键词文本 / 人群名 / 创意名 / 商品标题")
    @TableField("entity_name")
    private String entityName;

    @Schema(description = "该明细所属宝贝 id，与 platform_product.code 对得上")
    @TableField("item_id")
    private String itemId;

    @TableField("item_name")
    private String itemName;

    @TableField("campaign_id")
    private String campaignId;

    @TableField("campaign_name")
    private String campaignName;

    @TableField("unit_id")
    private String unitId;

    @TableField("unit_name")
    private String unitName;

    @TableField("report_source")
    private String reportSource;

    private BigDecimal charge;

    @TableField("ad_pv")
    private Long adPv;

    private Long click;

    @TableField("ctr_percent")
    private BigDecimal ctrPercent;

    private BigDecimal cpc;

    @TableField("gmv_total")
    private BigDecimal gmvTotal;

    @TableField("gmv_direct")
    private BigDecimal gmvDirect;

    @TableField("gmv_indirect")
    private BigDecimal gmvIndirect;

    @TableField("order_total")
    private Integer orderTotal;

    private BigDecimal roi;

    @TableField("cart_count")
    private Integer cartCount;

    @TableField("item_collect")
    private Integer itemCollect;

    @TableField("chat_count")
    private Integer chatCount;

    @TableField("raw_json")
    private String rawJson;

    @TableField("import_batch")
    private String importBatch;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
