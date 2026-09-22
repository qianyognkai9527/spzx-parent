package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("expense_order_tag")
public class ExpenseOrderTag {

    @TableField("order_id")
    private Long orderId;

    @TableField("tag_id")
    private Long tagId;
}
