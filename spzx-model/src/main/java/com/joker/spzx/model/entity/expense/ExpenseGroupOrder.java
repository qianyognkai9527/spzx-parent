package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("expense_group_order")
public class ExpenseGroupOrder {

    @TableField("group_id")
    private Long groupId;

    @TableField("order_id")
    private Long orderId;
}
