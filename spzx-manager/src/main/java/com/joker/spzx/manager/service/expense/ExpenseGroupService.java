package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ExpenseGroupMapper;
import com.joker.spzx.manager.mapper.ExpenseGroupOrderMapper;
import com.joker.spzx.manager.mapper.ExpenseOrderMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroup;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;

@Service
public class ExpenseGroupService extends ServiceImpl<ExpenseGroupMapper, ExpenseGroup> {

    @Autowired
    private ExpenseGroupMapper expenseGroupMapper;

    @Autowired
    private ExpenseGroupOrderMapper expenseGroupOrderMapper;

    @Autowired
    private ExpenseOrderMapper expenseOrderMapper;

    @Autowired
    private ExpenseOrderService expenseOrderService;

    public static class GroupDto {
        public String groupName;
        public String remark;
        public List<Long> orderIds;
    }

    public List<ExpenseGroupVo> listWithStats() {
        return expenseGroupMapper.listWithStats();
    }

    @Transactional
    public Long create(String groupName, String remark, List<Long> orderIds) {
        ExpenseGroup g = new ExpenseGroup();
        g.setGroupName(groupName.trim());
        g.setRemark(remark == null || remark.isBlank() ? null : remark.trim());
        expenseGroupMapper.insert(g);
        addOrders(g.getId(), orderIds);
        return g.getId();
    }

    @Transactional
    public void rename(Long id, String groupName, String remark) {
        ExpenseGroup row = expenseGroupMapper.selectById(id);
        if (row == null) {
            throw new IllegalArgumentException("分组不存在: " + id);
        }
        if (groupName != null && !groupName.isBlank()) {
            row.setGroupName(groupName.trim());
        }
        if (remark != null) {
            row.setRemark(remark.isBlank() ? null : remark.trim());
        }
        expenseGroupMapper.updateById(row);
    }

    @Transactional
    public void deleteGroup(Long id) {
        expenseGroupMapper.deleteById(id);
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getGroupId, id));
    }

    @Transactional
    public int addOrders(Long groupId, List<Long> orderIds) {
        List<Long> valid = validOrderIds(orderIds);
        int added = 0;
        for (Long oid : valid) {
            ExpenseGroupOrder link = new ExpenseGroupOrder();
            link.setGroupId(groupId);
            link.setOrderId(oid);
            try {
                expenseGroupOrderMapper.insert(link);
                added++;
            } catch (DuplicateKeyException e) {
                // 已在同组，幂等忽略
            }
        }
        return added;
    }

    @Transactional
    public void removeOrder(Long groupId, Long orderId) {
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getGroupId, groupId)
                .eq(ExpenseGroupOrder::getOrderId, orderId));
    }

    public Page<ExpenseOrderVo> pageOrders(long pageNum, long pageSize, Long groupId) {
        List<Long> ids = expenseGroupOrderMapper.selectList(new LambdaQueryWrapper<ExpenseGroupOrder>()
                        .eq(ExpenseGroupOrder::getGroupId, groupId)
                        .select(ExpenseGroupOrder::getOrderId))
                .stream().map(ExpenseGroupOrder::getOrderId).toList();
        return expenseOrderService.pageByIds(pageNum, pageSize, ids);
    }

    private List<Long> validOrderIds(List<Long> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            return new ArrayList<>();
        }
        List<Long> distinct = new ArrayList<>(new LinkedHashSet<>(orderIds.stream()
                .filter(java.util.Objects::nonNull).toList()));
        if (distinct.isEmpty()) {
            return distinct;
        }
        List<Long> exist = expenseOrderMapper.selectList(new LambdaQueryWrapper<ExpenseOrder>()
                        .in(ExpenseOrder::getId, distinct)
                        .select(ExpenseOrder::getId))
                .stream().map(ExpenseOrder::getId).toList();
        return exist;
    }
}
