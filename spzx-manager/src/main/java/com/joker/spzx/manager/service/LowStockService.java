package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.mapper.LowStockMapper;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import com.joker.spzx.model.vo.mall.LowStockSpecVo;
import com.joker.spzx.model.vo.mall.LowStockTaobaoItemVo;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 低库存规格页：source_sku 规格级库存现算，按货源分组，只显示铺货货源（taobao_offer_map EXISTS）。
 * 1358 行量级现算毫秒级，不建物化表——物化只换来滞后（推广日报同款结论）。
 * 唯一写入是人工处理标记（low_stock_handle，1=下架 2=删除 3=下架SKU）：
 * 用户在平台侧人工处理完后回来留痕，页面按钮不碰库存也不碰淘宝。
 */
@Service
public class LowStockService {

    /** 阈值三档（spec 定死）；<10 红是前端固定展示，与这里的档位无关 */
    public static final Set<Integer> THRESHOLDS = Set.of(10, 20, 50);
    public static final int DEFAULT_THRESHOLD = 20;

    /** 人工处理标记枚举（low_stock_handle.handle_type）：1=已下架 2=已删除 3=已下架SKU */
    public static final Set<Integer> HANDLE_TYPES = Set.of(1, 2, 3);

    /** 处理状态筛选：all=全部 pending=待处理 done=已处理（非法值回 all，仿 facet） */
    public static final Set<String> HANDLE_FILTERS = Set.of("all", "pending", "done");

    /** 失效筛选：no=按阈值正常视图 dead=货源失效视图（非法回 no，仿 facet） */
    public static final Set<String> DEAD_FILTERS = Set.of("no", "dead");

    @Autowired
    private LowStockMapper lowStockMapper;

    /** 白名单内原样通过；空/缺省回默认 20；白名单外回 null（调用方转 400），不静默放行 */
    public static Integer normalizeThreshold(String raw) {
        if (raw == null || raw.isBlank()) {
            return DEFAULT_THRESHOLD;
        }
        try {
            int v = Integer.parseInt(raw.trim());
            return THRESHOLDS.contains(v) ? v : null;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** 1/2/3 之外一律 null（调用方转 400）——人工留痕字段，脏值比缺更糟 */
    public static Integer normalizeHandleType(Integer raw) {
        return raw == null || !HANDLE_TYPES.contains(raw) ? null : raw;
    }

    /** 筛选不是数据：非法值退回 all（同 ItemOpsService.normalizeFacet），不 400 */
    public static String normalizeHandleFilter(String raw) {
        if (raw == null) {
            return "all";
        }
        String v = raw.trim();
        return HANDLE_FILTERS.contains(v) ? v : "all";
    }

    /** 失效筛选仿 facet：白名单 no/dead，非法/缺省回 no，不 400 */
    public static String normalizeDeadFilter(String raw) {
        if (raw == null) return "no";
        String v = raw.trim();
        return DEAD_FILTERS.contains(v) ? v : "no";
    }

    /** 缺省用 dft，越界夹取（同 ItemOpsService.normalizeInt 口径） */
    public static int normalizeInt(Integer raw, int dft, int min, int max) {
        if (raw == null) {
            return dft;
        }
        return Math.max(min, Math.min(max, raw));
    }

    public IPage<LowStockRowVo> list(String thresholdParam, String keyword, String handleStatus,
                                     String sourceDead, Integer page, Integer size) {
        // threshold 归一化照旧（失效视图忽略阈值，但白名单照校验，避免静默放行）
        Integer threshold = normalizeThreshold(thresholdParam);
        if (threshold == null) {
            throw new ServiceException(400, "阈值只支持 10/20/50");
        }
        long pageNum = normalizeInt(page, 1, 1, Integer.MAX_VALUE);
        long pageSize = normalizeInt(size, 20, 1, 100);
        String kw = (keyword == null || keyword.isBlank()) ? null : keyword.trim();

        String deadFilter = normalizeDeadFilter(sourceDead);
        boolean deadView = "dead".equals(deadFilter);
        IPage<LowStockRowVo> groups = deadView
                ? lowStockMapper.selectDeadGroups(new Page<>(pageNum, pageSize),
                        kw, normalizeHandleFilter(handleStatus))
                : lowStockMapper.selectLowStockGroups(new Page<>(pageNum, pageSize),
                        threshold, kw, normalizeHandleFilter(handleStatus));
        if (groups.getRecords().isEmpty()) {
            return groups;
        }
        Map<Long, LowStockRowVo> byId = new HashMap<>();
        List<Long> ids = new ArrayList<>();
        for (LowStockRowVo row : groups.getRecords()) {
            row.setTaobaoItems(new ArrayList<>());
            row.setLowSpecs(new ArrayList<>());
            byId.put(row.getSourceProductId(), row);
            ids.add(row.getSourceProductId());
        }
        for (LowStockTaobaoItemVo t : lowStockMapper.selectTaobaoItems(ids)) {
            LowStockRowVo row = byId.get(t.getSourceProductId());
            if (row != null) {
                row.getTaobaoItems().add(t.getTaobaoItemId());
                if (row.getOfferId() == null) {
                    row.setOfferId(t.getOfferId());
                }
            }
        }
        // 失效视图没有 SKU 行（死链建档时可能整档删光），低规格明细只属于正常视图
        if (!deadView) {
            for (LowStockSpecVo s : lowStockMapper.selectLowSpecs(ids, threshold)) {
                LowStockRowVo row = byId.get(s.getSourceProductId());
                if (row != null) {
                    row.getLowSpecs().add(s);
                }
            }
        }
        return groups;
    }

    /** 打处理标记（重复标记覆盖、时间刷新）；标记人取当前登录用户 */
    public void mark(Long sourceProductId, Integer handleType) {
        if (sourceProductId == null || sourceProductId <= 0) {
            throw new ServiceException(400, "sourceProductId 非法");
        }
        Integer type = normalizeHandleType(handleType);
        if (type == null) {
            throw new ServiceException(400, "处理方式只支持下架/删除/下架SKU");
        }
        lowStockMapper.upsertHandle(sourceProductId, type, AuthContextUtil.getUser().getId());
    }

    /** 撤销处理标记 */
    public void clear(Long sourceProductId) {
        if (sourceProductId == null || sourceProductId <= 0) {
            throw new ServiceException(400, "sourceProductId 非法");
        }
        lowStockMapper.clearHandle(sourceProductId);
    }
}
