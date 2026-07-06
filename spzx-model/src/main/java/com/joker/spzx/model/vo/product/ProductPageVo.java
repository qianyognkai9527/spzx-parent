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

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;
}
