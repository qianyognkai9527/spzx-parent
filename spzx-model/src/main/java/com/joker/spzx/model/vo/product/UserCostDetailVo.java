package com.joker.spzx.model.vo.product;


import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Schema(description = "账单详情VO")
public class UserCostDetailVo {

    @Schema(description = "ID")
    private Long id;

    @Schema(description = "收支用户主体")
    private Long userId;

    @Schema(description = "账单类型1:收入2:支出")
    private Integer billType;

    @Schema(description = "金额")
    private BigDecimal amount;

    @Schema(description = "支付方式")
    private Integer payType;

    @Schema(description = "用途Id")
    private Integer payUsageId;

    @Schema(description = "支付时间")
    private LocalDateTime payTime;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

    @Schema(description = "备注")
    private String remark;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    private Integer platformType;
}
