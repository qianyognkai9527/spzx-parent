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
 * 付费推广计划粒度日报。ingest_dataset 里 promo_cost 契约的目标表。
 *
 * 所有指标列都可空：报表导出不给某一列是常态（不同计划类型字段集不一样），
 * 空表示"不知道"，0 表示"报表给了 0"，两者不能混。
 */
@Data
@Schema(name = "PromoCostDaily", description = "付费推广计划粒度日报")
@TableName("promo_cost_daily")
public class PromoCostDaily {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "店铺 id，0=导入时未指定")
    @TableField("shop_id")
    private Long shopId;

    @TableField("platform_code")
    private Integer platformCode;

    @TableField("stat_date")
    private LocalDate statDate;

    @Schema(description = "keyword=关键词推广 crowd=人群推广 site=全站推广 other")
    @TableField("plan_type")
    private String planType;

    @TableField("campaign_id")
    private String campaignId;

    @TableField("campaign_name")
    private String campaignName;

    @TableField("report_source")
    private String reportSource;

    @Schema(description = "花费(元)")
    private BigDecimal charge;

    @TableField("ad_pv")
    private Long adPv;

    private Long click;

    @Schema(description = "点击率，百分数原样存：12.34 表示 12.34%")
    @TableField("ctr_percent")
    private BigDecimal ctrPercent;

    private BigDecimal cpc;

    private BigDecimal cpm;

    @TableField("gmv_total")
    private BigDecimal gmvTotal;

    @TableField("gmv_direct")
    private BigDecimal gmvDirect;

    @TableField("gmv_indirect")
    private BigDecimal gmvIndirect;

    @TableField("order_total")
    private Integer orderTotal;

    @TableField("order_direct")
    private Integer orderDirect;

    private BigDecimal roi;

    @TableField("cart_count")
    private Integer cartCount;

    @TableField("item_collect")
    private Integer itemCollect;

    @TableField("shop_collect")
    private Integer shopCollect;

    @TableField("chat_count")
    private Integer chatCount;

    @Schema(description = "整行原始键值 JSON，映射变更后可重放")
    @TableField("raw_json")
    private String rawJson;

    @TableField("import_batch")
    private String importBatch;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
