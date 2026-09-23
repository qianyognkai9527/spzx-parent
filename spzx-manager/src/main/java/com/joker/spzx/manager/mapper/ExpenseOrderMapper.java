package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.vo.expense.DailyAmountVo;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@Mapper
public interface ExpenseOrderMapper extends BaseMapper<ExpenseOrder> {

    @Select("SELECT COALESCE(SUM(amount),0) FROM expense_order WHERE expense_date BETWEEN #{begin} AND #{end}")
    BigDecimal sumBetween(@Param("begin") LocalDate begin, @Param("end") LocalDate end);

    @Select("SELECT COUNT(*) FROM expense_order WHERE expense_date BETWEEN #{begin} AND #{end}")
    Long countBetween(@Param("begin") LocalDate begin, @Param("end") LocalDate end);

    @Select("SELECT expense_date AS date, SUM(amount) AS amount FROM expense_order " +
            "WHERE expense_date >= #{begin} GROUP BY expense_date ORDER BY expense_date")
    List<DailyAmountVo> sumDailySince(@Param("begin") LocalDate begin);

    @Select("SELECT expense_date AS date, SUM(amount) AS amount FROM expense_order " +
            "WHERE expense_date >= #{begin} GROUP BY expense_date ORDER BY amount DESC LIMIT 1")
    DailyAmountVo maxDaySince(@Param("begin") LocalDate begin);

    @Select("SELECT id, title, amount, counterparty FROM expense_order " +
            "WHERE expense_date = #{date} ORDER BY amount DESC LIMIT 1")
    Map<String, Object> topOrderOfDay(@Param("date") LocalDate date);

    @Select("SELECT t.name FROM expense_order_tag ot JOIN expense_tag t ON t.id = ot.tag_id " +
            "WHERE ot.order_id = #{orderId} ORDER BY t.sort_value LIMIT 1")
    String firstTagNameOfOrder(@Param("orderId") Long orderId);

    @Select("SELECT MAX(expense_date) FROM expense_order WHERE source = 1")
    LocalDate lastImportDate();

    @Select("SELECT t.name AS name, SUM(o.amount) AS amount FROM expense_order o " +
            "JOIN expense_order_tag ot ON ot.order_id = o.id " +
            "JOIN expense_tag t ON t.id = ot.tag_id " +
            "WHERE o.expense_date >= #{begin} GROUP BY t.name ORDER BY amount DESC")
    List<Map<String, Object>> sumByTagSince(@Param("begin") LocalDate begin);

    @Select("SELECT channel AS name, SUM(amount) AS amount FROM expense_order " +
            "WHERE expense_date >= #{begin} GROUP BY channel ORDER BY amount DESC")
    List<Map<String, Object>> sumByChannelSince(@Param("begin") LocalDate begin);

    @Select("SELECT DATE_FORMAT(expense_date, '%Y-%m') AS name, SUM(amount) AS amount " +
            "FROM expense_order WHERE expense_date >= #{begin} AND expense_date < #{end} " +
            "GROUP BY DATE_FORMAT(expense_date, '%Y-%m') ORDER BY name")
    List<Map<String, Object>> sumMonthly(@Param("begin") LocalDate begin, @Param("end") LocalDate end);

    /** 批量导入：uk_trade_no 冲突静默跳过，返回实际插入行数（单语句即原子，无需包事务） */
    @Insert("<script>INSERT IGNORE INTO expense_order " +
            "(expense_date, txn_time, amount, channel, source, title, counterparty, alipay_trade_no, remark) VALUES " +
            "<foreach collection='rows' item='r' separator=','>" +
            "(#{r.expenseDate},#{r.txnTime},#{r.amount},#{r.channel},#{r.source},#{r.title},#{r.counterparty},#{r.alipayTradeNo},#{r.remark})" +
            "</foreach></script>")
    int insertIgnoreBatch(@Param("rows") List<ExpenseOrder> rows);
}
