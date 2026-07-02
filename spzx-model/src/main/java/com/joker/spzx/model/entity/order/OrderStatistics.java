package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@TableName("order_statistics")
@Schema(name = "OrderStatistics", description = "订单统计")
public class OrderStatistics extends BaseEntity {

    @Schema(description = "省份")
    @TableField("province_code")
    private String provinceCode;

    @Schema(description = "订单统计日期")
    @TableField("order_date")
    private LocalDate orderDate;

    @Schema(description = "总金额")
    @TableField("total_amount")
    private BigDecimal totalAmount;

    @Schema(description = "订单总数")
    @TableField("total_num")
    private Integer totalNum;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}