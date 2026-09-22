package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ExpenseGroupOrderMapper;
import com.joker.spzx.manager.mapper.ExpenseOrderMapper;
import com.joker.spzx.manager.mapper.ExpenseOrderTagMapper;
import com.joker.spzx.manager.mapper.ExpenseTagMapper;
import com.joker.spzx.model.entity.expense.ExpenseGroupOrder;
import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.entity.expense.ExpenseOrderTag;
import com.joker.spzx.model.entity.expense.ExpenseTag;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import com.joker.spzx.model.vo.expense.ImportResultVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class ExpenseOrderService extends ServiceImpl<ExpenseOrderMapper, ExpenseOrder> {

    @Autowired
    private ExpenseOrderMapper expenseOrderMapper;

    @Autowired
    private ExpenseOrderTagMapper expenseOrderTagMapper;

    @Autowired
    private ExpenseTagMapper expenseTagMapper;

    @Autowired
    private ExpenseGroupOrderMapper expenseGroupOrderMapper;

    private final AlipayBillCsvParser parser = new AlipayBillCsvParser();

    /** 手工录入 DTO */
    public static class OrderDto {
        public Long id;
        public LocalDate expenseDate;
        public java.time.LocalDateTime txnTime;
        public BigDecimal amount;
        public String channel;
        public String title;
        public String counterparty;
        public String remark;
        public List<Long> tagIds;
    }

    public Page<ExpenseOrderVo> page(long pageNum, long pageSize, LocalDate dateBegin, LocalDate dateEnd,
                                     String channel, Long tagId, String keyword) {
        LambdaQueryWrapper<ExpenseOrder> qw = new LambdaQueryWrapper<ExpenseOrder>();
        qw.ge(dateBegin != null, ExpenseOrder::getExpenseDate, dateBegin);
        qw.le(dateEnd != null, ExpenseOrder::getExpenseDate, dateEnd);
        qw.eq(channel != null && !channel.isBlank(), ExpenseOrder::getChannel, channel);
        if (keyword != null && !keyword.isBlank()) {
            String kw = keyword.trim();
            qw.and(w -> w.like(ExpenseOrder::getTitle, kw)
                    .or().like(ExpenseOrder::getCounterparty, kw)
                    .or().like(ExpenseOrder::getRemark, kw));
        }
        if (tagId != null) {
            List<Long> ids = orderIdsByTag(tagId);
            if (ids.isEmpty()) {
                return new Page<>(pageNum, pageSize);
            }
            qw.in(ExpenseOrder::getId, ids);
        }
        qw.orderByDesc(ExpenseOrder::getExpenseDate)
                .orderByDesc(ExpenseOrder::getTxnTime)
                .orderByDesc(ExpenseOrder::getId);

        Page<ExpenseOrder> page = expenseOrderMapper.selectPage(new Page<>(pageNum, pageSize), qw);
        Page<ExpenseOrderVo> out = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        out.setRecords(assembleVos(page.getRecords()));
        return out;
    }

    /** 按订单 id 集合分页（分组明细用），排序与列表页一致 */
    public Page<ExpenseOrderVo> pageByIds(long pageNum, long pageSize, List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return new Page<>(pageNum, pageSize);
        }
        LambdaQueryWrapper<ExpenseOrder> qw = new LambdaQueryWrapper<ExpenseOrder>()
                .in(ExpenseOrder::getId, ids)
                .orderByDesc(ExpenseOrder::getExpenseDate)
                .orderByDesc(ExpenseOrder::getTxnTime)
                .orderByDesc(ExpenseOrder::getId);
        Page<ExpenseOrder> page = expenseOrderMapper.selectPage(new Page<>(pageNum, pageSize), qw);
        Page<ExpenseOrderVo> out = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        out.setRecords(assembleVos(page.getRecords()));
        return out;
    }

    @Transactional
    public Long createManual(OrderDto dto) {
        ExpenseOrder row = new ExpenseOrder();
        applyDto(row, dto);
        row.setSource(2);
        expenseOrderMapper.insert(row);
        saveTags(row.getId(), dto.tagIds);
        return row.getId();
    }

    @Transactional
    public void update(Long id, OrderDto dto) {
        ExpenseOrder row = expenseOrderMapper.selectById(id);
        if (row == null) {
            throw new IllegalArgumentException("记录不存在: " + id);
        }
        applyDto(row, dto);
        row.setId(id);
        expenseOrderMapper.updateById(row);
        expenseOrderTagMapper.delete(new LambdaQueryWrapper<ExpenseOrderTag>()
                .eq(ExpenseOrderTag::getOrderId, id));
        saveTags(id, dto.tagIds);
    }

    @Transactional
    public void delete(Long id) {
        expenseOrderMapper.deleteById(id);
        expenseOrderTagMapper.delete(new LambdaQueryWrapper<ExpenseOrderTag>()
                .eq(ExpenseOrderTag::getOrderId, id));
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .eq(ExpenseGroupOrder::getOrderId, id));
    }

    @Transactional
    public int batchDelete(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return 0;
        }
        int n = expenseOrderMapper.deleteByIds(ids);
        expenseOrderTagMapper.delete(new LambdaQueryWrapper<ExpenseOrderTag>()
                .in(ExpenseOrderTag::getOrderId, ids));
        expenseGroupOrderMapper.delete(new LambdaQueryWrapper<ExpenseGroupOrder>()
                .in(ExpenseGroupOrder::getOrderId, ids));
        return n;
    }

    /** 支付宝 CSV 导入：口径过滤在解析器；交易号 DB 唯一键去重（预查 + 异常兜底），幂等 */
    @Transactional
    public ImportResultVo importAlipayCsv(MultipartFile file) {
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (Exception e) {
            throw new IllegalArgumentException("读取上传文件失败: " + e.getMessage());
        }
        AlipayBillCsvParser.ParseResult pr = parser.parse(bytes);

        ImportResultVo out = new ImportResultVo();
        out.setTotal(pr.total);
        out.setSkippedNonExpense(pr.skippedNonExpense);
        out.setSkippedClosed(pr.skippedClosed);
        out.setSkippedZero(pr.skippedZero);
        out.getErrors().addAll(pr.errors);

        // 预查已存在的交易号
        Set<String> existing = new HashSet<>();
        List<String> allNos = pr.rows.stream().map(r -> r.tradeNo).toList();
        for (int from = 0; from < allNos.size(); from += 500) {
            List<String> part = allNos.subList(from, Math.min(allNos.size(), from + 500));
            if (!part.isEmpty()) {
                List<ExpenseOrder> hit = expenseOrderMapper.selectList(new LambdaQueryWrapper<ExpenseOrder>()
                        .in(ExpenseOrder::getAlipayTradeNo, part)
                        .select(ExpenseOrder::getAlipayTradeNo));
                hit.forEach(o -> existing.add(o.getAlipayTradeNo()));
            }
        }

        for (AlipayBillCsvParser.ParsedRow r : pr.rows) {
            if (existing.contains(r.tradeNo)) {
                out.setSkippedDuplicate(out.getSkippedDuplicate() + 1);
                continue;
            }
            ExpenseOrder row = new ExpenseOrder();
            row.setExpenseDate(r.expenseDate);
            row.setTxnTime(r.txnTime);
            row.setAmount(r.amount);
            row.setChannel("支付宝");
            row.setSource(1);
            row.setTitle(r.title);
            row.setCounterparty(r.counterparty);
            row.setAlipayTradeNo(r.tradeNo);
            try {
                expenseOrderMapper.insert(row);
                out.setImported(out.getImported() + 1);
            } catch (DuplicateKeyException e) {
                // 并发或预查遗漏：唯一键兜底
                out.setSkippedDuplicate(out.getSkippedDuplicate() + 1);
            }
        }
        return out;
    }

    private List<Long> orderIdsByTag(Long tagId) {
        List<ExpenseOrderTag> links = expenseOrderTagMapper.selectList(new LambdaQueryWrapper<ExpenseOrderTag>()
                .eq(ExpenseOrderTag::getTagId, tagId)
                .select(ExpenseOrderTag::getOrderId));
        return links.stream().map(ExpenseOrderTag::getOrderId).toList();
    }

    private List<ExpenseOrderVo> assembleVos(List<ExpenseOrder> rows) {
        if (rows == null || rows.isEmpty()) {
            return Collections.emptyList();
        }
        List<Long> ids = rows.stream().map(ExpenseOrder::getId).toList();
        List<ExpenseOrderTag> links = expenseOrderTagMapper.selectByOrderIds(ids);
        Map<Long, List<Long>> tagIdsByOrder = new HashMap<>();
        for (ExpenseOrderTag l : links) {
            tagIdsByOrder.computeIfAbsent(l.getOrderId(), k -> new ArrayList<>()).add(l.getTagId());
        }
        Map<Long, ExpenseTag> tagById = new HashMap<>();
        if (!links.isEmpty()) {
            Set<Long> tagIds = new HashSet<>(links.stream().map(ExpenseOrderTag::getTagId).toList());
            for (ExpenseTag t : expenseTagMapper.selectBatchIds(tagIds)) {
                tagById.put(t.getId(), t);
            }
        }
        List<ExpenseOrderVo> out = new ArrayList<>();
        for (ExpenseOrder row : rows) {
            ExpenseOrderVo vo = new ExpenseOrderVo();
            vo.setId(row.getId());
            vo.setExpenseDate(row.getExpenseDate());
            vo.setTxnTime(row.getTxnTime());
            vo.setAmount(row.getAmount());
            vo.setChannel(row.getChannel());
            vo.setSource(row.getSource());
            vo.setTitle(row.getTitle());
            vo.setCounterparty(row.getCounterparty());
            vo.setAlipayTradeNo(row.getAlipayTradeNo());
            vo.setRemark(row.getRemark());
            vo.setCreateTime(row.getCreateTime());
            vo.setUpdateTime(row.getUpdateTime());
            List<Long> tIds = tagIdsByOrder.getOrDefault(row.getId(), Collections.emptyList());
            vo.setTagIds(tIds);
            List<String> names = new ArrayList<>();
            List<String> colors = new ArrayList<>();
            for (Long tid : tIds) {
                ExpenseTag t = tagById.get(tid);
                if (t != null) {
                    names.add(t.getName());
                    colors.add(t.getColor());
                }
            }
            vo.setTagNames(names);
            vo.setTagColors(colors);
            out.add(vo);
        }
        return out;
    }

    private void saveTags(Long orderId, List<Long> tagIds) {
        if (tagIds == null || tagIds.isEmpty()) {
            return;
        }
        for (Long tid : new HashSet<>(tagIds)) {
            ExpenseOrderTag link = new ExpenseOrderTag();
            link.setOrderId(orderId);
            link.setTagId(tid);
            expenseOrderTagMapper.insert(link);
        }
    }

    private void applyDto(ExpenseOrder row, OrderDto dto) {
        if (dto.amount == null || dto.amount.signum() <= 0) {
            throw new IllegalArgumentException("金额必须大于 0");
        }
        if (dto.expenseDate == null) {
            throw new IllegalArgumentException("消费日期不能为空");
        }
        String ch = dto.channel == null || dto.channel.isBlank() ? "其他" : dto.channel.trim();
        row.setExpenseDate(dto.expenseDate);
        row.setTxnTime(dto.txnTime);
        row.setAmount(dto.amount);
        row.setChannel(ch);
        row.setTitle(dto.title);
        row.setCounterparty(dto.counterparty);
        row.setRemark(dto.remark);
    }
}
