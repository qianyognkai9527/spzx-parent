package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 对账关账月份：表中存在 yyyy-MM 行即视为该月已关账，账单禁改禁删、导入跳过。
 */
@Data
@TableName("expense_period_close")
public class ExpensePeriodClose {

    @TableId(value = "period", type = IdType.INPUT)
    private String period;

    @TableField("closed_by")
    private Long closedBy;

    @TableField("closed_time")
    private LocalDateTime closedTime;

    private String remark;
}
