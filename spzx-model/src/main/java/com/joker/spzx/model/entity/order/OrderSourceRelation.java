package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "本地订单与货源订单关联实体类")
public class OrderSourceRelation extends BaseEntity {

    @Schema(description = "本地订单号")
    @TableField("order_no")
    private String orderNo;

    @Schema(description = "货源订单号")
    @TableField("source_order_no")
    private String sourceOrderNo;

    @Schema(description = "平台类型（1:淘宝 2:抖音）")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

}
