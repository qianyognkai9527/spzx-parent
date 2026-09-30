package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Schema(name = "ExpenseTagRule", description = "账单自动打标规则")
@TableName("expense_tag_rule")
public class ExpenseTagRule {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "命中后打上的标签 id")
    @TableField("tag_id")
    private Long tagId;

    @Schema(description = "比对字段：counterparty|title|remark|channel")
    @TableField("match_field")
    private String matchField;

    @Schema(description = "匹配方式：eq=全等 like=包含")
    @TableField("match_type")
    private String matchType;

    @TableField("keyword")
    private String keyword;

    @Schema(description = "金额下限（含），空=不限")
    @TableField("min_amount")
    private BigDecimal minAmount;

    @Schema(description = "金额上限（含），空=不限")
    @TableField("max_amount")
    private BigDecimal maxAmount;

    @Schema(description = "1=启用 0=停用")
    @TableField("status")
    private Integer status;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;

    /** 标签名：给规则列表页显示的，不落库 */
    @TableField(exist = false)
    private String tagName;
}
