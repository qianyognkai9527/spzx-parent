package com.joker.spzx.model.dto.mall;


import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class MallAddOrderPageVo {

    @Schema(description = "主键")
    private Long id;

    @Schema(description = "刷手Id")
    private Long brushPersonId;

    @Schema(description = "刷手名称")
    private String brushPersonName;

    @Schema(description = "产品Id")
    private String productId;

    @Schema(description = "主图图片地址")
    private String productPicUrl;

    @Schema(description = "产品名称")
    private String productName;

    @Schema(description = "淘宝订单号")
    private String tbOrderId;

    @Schema(description = "下单时间")
    private LocalDateTime orderTime;

    @Schema(description = "订单状态")
    private Integer orderState;

    @Schema(description = "本金")
    private Double seedMoney;

    @Schema(description = "佣金")
    private Double hireMoney;

    @Schema(description = "运费")
    private Double wayBillMoney;

    @Schema(description = "物流单号")
    private String wayBillCode;

    @Schema(description = "物流公司")
    private String wayBillName;

    @Schema(description = "平台类型：1-淘宝,2-抖音")
    private Integer platformType;

    @Schema(description = "佣金是否已返：0-未返,1-已返")
    private Integer hireIsPay;

    @Schema(description = "是否已评价：0-未评价,1-已评价")
    private Integer isEvaluated;

    @Schema(description = "本金是否已返：0-未返,1-已返")
    private Integer seedIsPay;

    @Schema(description = "返佣时间")
    private LocalDateTime settlementTime;
}
