package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class DailyAmountVo {

    private LocalDate date;

    private BigDecimal amount;
}
