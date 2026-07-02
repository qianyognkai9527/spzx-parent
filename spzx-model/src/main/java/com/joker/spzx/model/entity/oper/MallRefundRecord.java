package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * <p>
 * 退款分析报表
 * </p>
 *
 * @author joker
 * @since 2025-07-10 13:49:10
 */
@Getter
@Setter
@TableName("mall_refund_record")
@Schema(name = "MallRefundRecord", description = "退款分析报表")
public class MallRefundRecord extends Model<MallRefundRecord> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "报表编码")
    @TableField("code")
    private String code;

    @Schema(description = "报表名称")
    @TableField("name")
    private String name;

    @Schema(description = "起止日期")
    @TableField("start_time")
    private LocalDateTime startTime;

    @Schema(description = "结束日期")
    @TableField("end_time")
    private LocalDateTime endTime;

    @Schema(description = "支付总金额")
    @TableField("total_amount")
    private BigDecimal totalAmount;

    @Schema(description = "智能推广花费")
    @TableField("smart_promotion")
    private BigDecimal smartPromotion;

    @Schema(description = "佣金")
    @TableField("crowd_promotion")
    private BigDecimal crowdPromotion;

    @Schema(description = "运费")
    @TableField("site_promotion")
    private BigDecimal sitePromotion;

    @Schema(description = "物流单号")
    @TableField("keyword_promotion")
    private BigDecimal keywordPromotion;

    @Schema(description = "关联订单文件")
    @TableField("order_data_code")
    private String orderDataCode;

    @Schema(description = "状态（1：未生成2：生成中3：已生成")
    @TableField("state")
    private Integer state;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新人")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "创建时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "删除标识")
    @TableField("del_flag")
    private Integer delFlag;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
