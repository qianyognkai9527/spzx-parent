package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroup;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ExpenseGroupMapper extends BaseMapper<ExpenseGroup> {

    @Select("SELECT g.id, g.group_name, g.remark, g.create_time, " +
            "COUNT(go.order_id) AS totalCount, COALESCE(SUM(o.amount), 0) AS totalAmount, " +
            "MIN(o.expense_date) AS minDate, MAX(o.expense_date) AS maxDate " +
            "FROM expense_group g " +
            "LEFT JOIN expense_group_order go ON go.group_id = g.id " +
            "LEFT JOIN expense_order o ON o.id = go.order_id " +
            "GROUP BY g.id, g.group_name, g.remark, g.create_time " +
            "ORDER BY g.id DESC")
    List<ExpenseGroupVo> listWithStats();
}
