package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 本地订单 ↔ 货源订单 绑定关系表
 */
@Data
@EqualsAndHashCode(callSuper = true)
@TableName("order_bind")
public class OrderBind extends BaseEntity {

    private Long localOrderId;

    private String localOrderNo;

    private Long sourceOrderId;

    private String sourceOrderNo;

    private Integer sourceType;

    private Integer bindStatus;

    private String remark;
}
