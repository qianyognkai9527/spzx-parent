package com.joker.spzx.model.entity.order;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@TableName("order_log")
@Schema(name = "OrderLog", description = "订单操作日志记录")
public class OrderLog extends BaseEntity {

    private static final long serialVersionUID = 1L;

    @Schema(description = "订单id")
    @TableField("order_id")
    private Long orderId;

    @Schema(description = "操作人：用户；系统；后台管理员")
    @TableField("operate_user")
    private String operateUser;

    @Schema(description = "订单状态")
    @TableField("process_status")
    private Integer processStatus;

    @Schema(description = "备注")
    @TableField("note")
    private String note;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}