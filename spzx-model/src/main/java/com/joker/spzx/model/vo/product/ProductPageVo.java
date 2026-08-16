package com.joker.spzx.model.vo.product;


import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class ProductPageVo {


    @Schema(description = "ID唯一标识")
    private Long id;

    @Schema(description = "货源商品名称")
    private String sourceProductName;

    @Schema(description = "货源厂商Id")
    private Long productFactoryId;

    @Schema(description = "货源厂商名称")
    private String productFactoryName;

    @Schema(description = "货源商品Id")
    private String sourceProductCode;

    @Schema(description = "货源商品链接地址")
    private String sourceProductUrl;

    @Schema(description = "头图链接地址")
    private String headImgUrl;

    @Schema(description = "发货物流公司")
    private String logisticsName;

    @Schema(description = "运费")
    private BigDecimal freightCost;

    @Schema(description = "货源价格")
    private BigDecimal sourcePrice;

    @Schema(description = "发货时长")
    private Integer dispatchTime;

    @Schema(description = "稳定状态：1-稳定，1-不太稳定，3-不稳定")
    private Integer steadyStatus;

    @Schema(description = "带图评价数量")
    private Integer evalWithImageCount;

    @Schema(description = "供应商名称(爬虫)")
    private String supplierName;

    @Schema(description = "回头率%(爬虫)")
    private BigDecimal repurchaseRate;

    @Schema(description = "全网销量(爬虫)")
    private Integer salesCount;

    @Schema(description = "近14天销量(累计差值)")
    private Integer salesCount14d;

    @Schema(description = "类目(爬虫)")
    private String categoryName;

    @Schema(description = "关键词(爬虫)")
    private String keyword;

    @Schema(description = "诚信通年限(爬虫)")
    private Integer trustYears;

    @Schema(description = "关联source_factory(爬虫厂家)")
    private Long sourceFactoryId;

    @Schema(description = "采集时间")
    private java.time.LocalDateTime crawlTime;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;

    @Schema(description = "数据来源:1=1688搜索候选 2=ISV已铺货")
    private Integer dataSource;

    @Schema(description = "优质等级:A/B/C NULL=未达标")
    private String qualityGrade;
}
