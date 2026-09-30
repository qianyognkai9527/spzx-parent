package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseOrderTag;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ExpenseOrderTagMapper extends BaseMapper<ExpenseOrderTag> {

    List<ExpenseOrderTag> selectByOrderIds(@Param("orderIds") List<Long> orderIds);

    /** 自动打标批量写：(order_id, tag_id) 主键冲突静默跳过，重复跑同一批规则只影响 0 行 */
    @Insert("<script>INSERT IGNORE INTO expense_order_tag (order_id, tag_id) VALUES " +
            "<foreach collection='rows' item='r' separator=','>(#{r.orderId},#{r.tagId})</foreach></script>")
    int insertIgnoreBatch(@Param("rows") List<ExpenseOrderTag> rows);
}
