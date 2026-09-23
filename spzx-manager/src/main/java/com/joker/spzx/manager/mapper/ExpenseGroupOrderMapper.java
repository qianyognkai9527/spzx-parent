package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ExpenseGroupOrderMapper extends BaseMapper<ExpenseGroupOrder> {

    /** 联合主键冲突静默跳过，返回实际插入行数（建组即加入/批量加单用） */
    @Insert("<script>INSERT IGNORE INTO expense_group_order (group_id, order_id) VALUES " +
            "<foreach collection='rows' item='r' separator=','>(#{r.groupId},#{r.orderId})</foreach></script>")
    int insertIgnoreBatch(@Param("rows") List<ExpenseGroupOrder> rows);
}
