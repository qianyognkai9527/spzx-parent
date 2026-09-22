package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseOrderTag;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ExpenseOrderTagMapper extends BaseMapper<ExpenseOrderTag> {

    List<ExpenseOrderTag> selectByOrderIds(@Param("orderIds") List<Long> orderIds);
}
