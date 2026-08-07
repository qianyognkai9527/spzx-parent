package com.joker.spzx.model.entity.pay;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("merchant_notify_record")
@Schema(name = "MerchantNotifyRecord", description = "商户回调通知记录")
public class MerchantNotifyRecord extends BaseEntity {

    @Schema(description = "订单号")
    @TableField("order_no")
    private String orderNo;

    @Schema(description = "通知类型: PAY/REFUND")
    @TableField("notify_type")
    private String notifyType;

    @Schema(description = "通知地址")
    @TableField("notify_url")
    private String notifyUrl;

    @Schema(description = "通知内容")
    @TableField("notify_content")
    private String notifyContent;

    @Schema(description = "通知次数")
    @TableField("notify_count")
    private Integer notifyCount;

    @Schema(description = "通知状态: 0-pending 1-success 2-fail")
    @TableField("notify_status")
    private Integer notifyStatus;

    @Schema(description = "下次通知时间")
    @TableField("next_notify_time")
    private LocalDateTime nextNotifyTime;

    @Schema(description = "响应内容")
    @TableField("response_content")
    private String responseContent;
}
