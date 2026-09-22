package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ExpenseTagMapper;
import com.joker.spzx.model.entity.expense.ExpenseTag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ExpenseTagService extends ServiceImpl<ExpenseTagMapper, ExpenseTag> {

    @Autowired
    private ExpenseTagMapper expenseTagMapper;

    public List<ExpenseTag> listAll() {
        return expenseTagMapper.selectList(new LambdaQueryWrapper<ExpenseTag>()
                .orderByAsc(ExpenseTag::getSortValue)
                .orderByAsc(ExpenseTag::getId));
    }

    /** name 唯一校验（excludeId 用于编辑排除自身）；合法返回 null，否则返回错误消息 */
    public String nameConflict(String name, Long excludeId) {
        Long cnt = expenseTagMapper.selectCount(new LambdaQueryWrapper<ExpenseTag>()
                .eq(ExpenseTag::getName, name)
                .ne(excludeId != null, ExpenseTag::getId, excludeId));
        return cnt != null && cnt > 0 ? "标签名已存在: " + name : null;
    }
}
