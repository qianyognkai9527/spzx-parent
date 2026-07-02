package com.joker.spzx.model.entity.user;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * <p>
 * 商品规格
 * </p>
 *
 * @author joker
 * @since 2025-08-25 16:12:25
 */
@Getter
@Setter
@TableName("user_cost")
@Schema(name = "UserCost", description = "商品规格")
public class UserCost extends Model<UserCost> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "ID")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "收支用户主体")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "账单类型1:收入2:支出")
    @TableField("bill_type")
    private Integer billType;

    @Schema(description = "创建时间")
    @TableField("amount")
    private BigDecimal amount;

    @Schema(description = "支付方式")
    @TableField("pay_type")
    private Integer payType;

    @Schema(description = "用途Id")
    @TableField("pay_usage_id")
    private Integer payUsageId;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "删除标记（0:不可用 1:可用）")
    @TableField("is_deleted")
    private Integer isDeleted;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("pay_time")
    private LocalDateTime payTime;

    @TableField("create_by")
    private Long createBy;

    @TableField("update_by")
    private Long updateBy;

    @TableField("remark")
    private String remark;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}
