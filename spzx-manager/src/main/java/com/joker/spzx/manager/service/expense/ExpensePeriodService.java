package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.ExpensePeriodCloseMapper;
import com.joker.spzx.model.entity.expense.ExpensePeriodClose;
import com.joker.spzx.utils.AuthContextUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.time.format.DateTimeParseException;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 对账关账：expense_period_close 中存在某月即锁定该月。
 * 关账后该月账单禁止改动/删除，重复导入的旧月行会被跳过（幂等，不误伤新行）。
 */
@Slf4j
@Service
public class ExpensePeriodService {

    @Autowired
    private ExpensePeriodCloseMapper mapper;

    public List<ExpensePeriodClose> list() {
        return mapper.selectList(new LambdaQueryWrapper<ExpensePeriodClose>()
                .orderByDesc(ExpensePeriodClose::getPeriod));
    }

    public Set<String> closedPeriods() {
        Set<String> out = new HashSet<>();
        mapper.selectList(null).forEach(r -> out.add(r.getPeriod()));
        return out;
    }

    public boolean isClosed(LocalDate date) {
        return date != null && isClosed(YearMonth.from(date).toString());
    }

    public boolean isClosed(String period) {
        return period != null && mapper.selectById(period) != null;
    }

    /** 关账前校验格式，避免脏 period 进主键 */
    public void close(String period, String remark) {
        YearMonth.parse(period); // 非法格式抛 DateTimeParseException
        if (mapper.selectById(period) != null) {
            throw new IllegalArgumentException("该月已关账: " + period);
        }
        ExpensePeriodClose e = new ExpensePeriodClose();
        e.setPeriod(period);
        e.setClosedBy(AuthContextUtil.getUser().getId());
        e.setClosedTime(LocalDateTime.now());
        e.setRemark(remark);
        mapper.insert(e);
        log.info("对账关账: period={} by={}", period, e.getClosedBy());
    }

    public void reopen(String period) {
        if (mapper.selectById(period) == null) {
            throw new IllegalArgumentException("该月未关账: " + period);
        }
        mapper.deleteById(period);
        log.info("对账反关账: period={}", period);
    }

    public static String monthOf(LocalDate date) {
        return date == null ? null : YearMonth.from(date).toString();
    }
}
