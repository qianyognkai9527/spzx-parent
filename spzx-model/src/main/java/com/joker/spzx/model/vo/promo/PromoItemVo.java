package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 宝贝维度的推广聚合 —— 付费/免费流量归因的落点。
 *
 * 一个「单元」就是一个「宝贝」，item_id 即淘宝商品ID，与 platform_product.code 同形。
 * platformProduct 为 false 表示这个投了钱的宝贝在本地商品表里找不到（对不上账，得单独看）。
 */
@Data
@Schema(description = "宝贝维度推广区间聚合")
public class PromoItemVo {

    private String itemId;

    @Schema(description = "推广侧带回的商品标题")
    private String itemName;

    @Schema(description = "本地平台商品表里的标题（与推广标题不一致时以本地为准）")
    private String productTitle;

    @Schema(description = "能否在 platform_product 里找到")
    private Boolean platformProduct;

    @Schema(description = "本地定价，null=未定价")
    private BigDecimal pricing;

    private String planType;

    @Schema(description = "投放该宝贝的计划ID，多个用逗号连接（一个宝贝可同时挂在 2 个计划上）")
    private String campaignId;

    @Schema(description = "投放该宝贝的计划数，>1 时 campaignId/campaignName 都是多值")
    private Integer campaignCount;

    @Schema(description = "投放该宝贝的计划名，多个用、连接")
    private String campaignName;

    @Schema(description = "区间内有数据的天数")
    private Integer days;

    private BigDecimal charge;

    private Long adPv;

    private Long click;

    private BigDecimal ctrPercent;

    private BigDecimal cpc;

    private BigDecimal gmvTotal;

    @Schema(description = "直接成交金额（点了广告才成交）")
    private BigDecimal gmvDirect;

    @Schema(description = "间接成交金额（点了广告后别的路径成交）")
    private BigDecimal gmvIndirect;

    private Integer orderTotal;

    private BigDecimal roi;

    private Integer cartCount;

    private Integer collectTotal;
}
