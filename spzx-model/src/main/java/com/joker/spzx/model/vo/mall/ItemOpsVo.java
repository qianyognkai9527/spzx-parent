package com.joker.spzx.model.vo.mall;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "商品运营台行：平台商品 + 近7日效果 + 货源成本与毛利预估")
public class ItemOpsVo {

    @Schema(description = "平台商品 id")
    private Long id;

    @Schema(description = "平台商品编号（淘宝 item_id / 抖店商品 id）")
    private String code;

    private String title;

    @Schema(description = "1-淘宝 2-抖音")
    private Integer platformType;

    @Schema(description = "所属店铺 id")
    private Long shopId;

    @Schema(description = "售价")
    private BigDecimal pricing;

    @Schema(description = "运费")
    private BigDecimal freight;

    @Schema(description = "近7日访客，无生意参谋数据为 null")
    private Long visitors;

    @Schema(description = "近7日成交金额")
    private BigDecimal payAmount;

    @Schema(description = "近7日成交买家数")
    private Integer payBuyers;

    @Schema(description = "近7日加购人数")
    private Integer cartUsers;

    @Schema(description = "效果数据快照时间")
    private String effectAt;

    @Schema(description = "绑定的货源商品数，0=没绑货源")
    private Integer sourceCount;

    @Schema(description = "货源最低进价（已绑定货源里取最低 SKU 价，无 SKU 时用货源商品报价）")
    private BigDecimal sourcePrice;

    @Schema(description = "货源最低库存")
    private Integer minStock;

    @Schema(description = "货源类目名")
    private String categoryName;

    @Schema(description = "平台技术服务费率 %（按平台下各类目均值）")
    private BigDecimal commissionRate;

    @Schema(description = "支付费率 %")
    private BigDecimal paymentFeeRate;

    @Schema(description = "预估单件毛利 = 售价 - 进价 - 售价*(佣金+支付费)/100；缺售价或进价为 null")
    private BigDecimal margin;

    @Schema(description = "预估毛利率 %")
    private BigDecimal marginRate;
}
