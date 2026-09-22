package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class ExpenseGroupVo {

    private Long id;

    private String groupName;

    private String remark;

    private Integer totalCount;

    private BigDecimal totalAmount;

    private LocalDate minDate;

    private LocalDate maxDate;

    private LocalDateTime createTime;
}
