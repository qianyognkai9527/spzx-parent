package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.mapper.ItemOpsMapper;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.vo.mall.ItemOpsVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Set;

/**
 * 商品运营台查询。
 *
 * 只做只读汇总：平台商品 × 生意参谋近7日效果 × 绑定货源成本。
 * 这一页不改数据、不写库，运营动作（改价/改标题/绑货源）仍在平台商品页做。
 */
@Service
public class ItemOpsService {

    /** 筛选项白名单。非法值不报错而是退回 all，避免前端一个拼错就整页空 */
    private static final Set<String> FACETS =
            Set.of("all", "noSale", "negativeMargin", "lowStock", "noEffect", "noSource", "unpriced");

    @Autowired
    private ItemOpsMapper itemOpsMapper;

    public static String normalizeFacet(String facet) {
        if (facet == null) {
            return "all";
        }
        String trimmed = facet.trim();
        return FACETS.contains(trimmed) ? trimmed : "all";
    }

    /** 阈值给默认值并夹在合理区间，避免一次全表扫出无意义的空结果 */
    public static int normalizeInt(Integer value, int fallback, int min, int max) {
        if (value == null) {
            return fallback;
        }
        return Math.min(Math.max(value, min), max);
    }

    public IPage<ItemOpsVo> page(long pageNum, long pageSize, Integer platformType, Long shopId,
                                 String keyword, String facet, Integer stockThreshold, Integer uvFrom) {
        // 分页钳制交给 PageQueryUtil，这里只管业务参数
        Page<ItemOpsVo> mpPage = PageQueryUtil.of(pageNum, pageSize);
        // 关掉 count 优化：这条 SQL 的 count 只能整条包成子查询。优化器会剥掉 join 和 select 列表，
        // 把派生表列名（margin/effectAt）留在外层 WHERE 里，报 Unknown column
        mpPage.setOptimizeCountSql(false);
        return itemOpsMapper.pageItems(
                mpPage,
                platformType,
                shopId,
                keyword == null || keyword.isBlank() ? null : keyword.trim(),
                normalizeFacet(facet),
                normalizeInt(stockThreshold, 10, 0, 1_000_000),
                normalizeInt(uvFrom, 0, 0, 1_000_000_000));
    }

    /** 筛选项上的数字：一次查询算齐，口径与 pageItems 的筛选条件一致 */
    public Map<String, Object> facetCounts(Integer platformType, Long shopId, String keyword,
                                           Integer stockThreshold, Integer uvFrom) {
        return itemOpsMapper.selectFacetCounts(
                platformType,
                shopId,
                keyword == null || keyword.isBlank() ? null : keyword.trim(),
                normalizeInt(stockThreshold, 10, 0, 1_000_000),
                normalizeInt(uvFrom, 0, 0, 1_000_000_000));
    }
}
