package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class ExpenseOrderVo {

    private Long id;

    private LocalDate expenseDate;

    private LocalDateTime txnTime;

    private BigDecimal amount;

    private String channel;

    private Integer source;

    private String title;

    private String counterparty;

    private String alipayTradeNo;

    private String remark;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    private List<Long> tagIds;

    private List<String> tagNames;

    private List<String> tagColors;
}
