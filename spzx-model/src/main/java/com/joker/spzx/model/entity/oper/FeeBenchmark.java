package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.math.BigDecimal;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("fee_benchmark")
public class FeeBenchmark extends BaseEntity {
    private Integer platformType;
    private String categoryName;
    private BigDecimal commissionRate;
    private BigDecimal paymentFeeRate;
    private BigDecimal freightInsurance;
    private String remark;
}
