package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.expense.ExpenseTagRule;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ExpenseTagRuleMapper extends BaseMapper<ExpenseTagRule> {

    /** 规则列表带上标签名，供「自动打标规则」表格直接渲染 */
    @Select("SELECT r.*, t.name AS tag_name FROM expense_tag_rule r " +
            "LEFT JOIN expense_tag t ON t.id = r.tag_id " +
            "ORDER BY r.status DESC, r.match_field, r.id")
    List<ExpenseTagRule> selectAllWithTagName();
}
