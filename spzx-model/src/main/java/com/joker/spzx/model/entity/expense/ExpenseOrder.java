package com.joker.spzx.model.entity.expense;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
@TableName("expense_order")
public class ExpenseOrder extends Model<ExpenseOrder> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("expense_date")
    private LocalDate expenseDate;

    @TableField("txn_time")
    private LocalDateTime txnTime;

    @TableField("amount")
    private BigDecimal amount;

    @TableField("channel")
    private String channel;

    @TableField("source")
    private Integer source;

    @TableField("title")
    private String title;

    @TableField("counterparty")
    private String counterparty;

    @TableField("alipay_trade_no")
    private String alipayTradeNo;

    @TableField("remark")
    private String remark;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
