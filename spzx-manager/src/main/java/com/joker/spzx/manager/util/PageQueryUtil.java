package com.joker.spzx.manager.util;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;

/**
 * 分页查询工具：统一收敛 "new Page<>(pageNum, pageSize) + page/selectPage" 样板
 */
public final class PageQueryUtil {

    /** 单页最大条数，与分页插件 maxLimit 保持一致 */
    public static final long MAX_PAGE_SIZE = 500;

    private PageQueryUtil() {
    }

    /**
     * 构造安全的分页对象：size<0 会被 MyBatis-Plus 解释为"不加 LIMIT 返回全表"，
     * 因此对 pageNum/pageSize 统一钳制（null 或非法值回退为 1/10，pageSize 上限 500）
     */
    public static <T> Page<T> of(Integer pageNum, Integer pageSize) {
        return of(pageNum == null ? 1 : pageNum.longValue(),
                pageSize == null ? 10 : pageSize.longValue());
    }

    public static <T> Page<T> of(long pageNum, long pageSize) {
        long current = pageNum < 1 ? 1 : pageNum;
        long size = pageSize < 1 ? 10 : Math.min(pageSize, MAX_PAGE_SIZE);
        return new Page<>(current, size);
    }

    /**
     * IService 分页查询（wrapper 可为 null，等价于无条件的 page(page)）；
     * E 由调用方赋值目标推断（IPage 或 Page），运行时对象即为本次构造的 Page，强转安全
     */
    @SuppressWarnings("unchecked")
    public static <T, E extends IPage<T>> E page(IService<T> service, Integer pageNum, Integer pageSize, Wrapper<T> wrapper) {
        Page<T> page = of(pageNum, pageSize);
        return (E) service.page(page, wrapper);
    }

    /**
     * BaseMapper 分页查询（同上）
     */
    @SuppressWarnings("unchecked")
    public static <T, E extends IPage<T>> E page(BaseMapper<T> mapper, Integer pageNum, Integer pageSize, Wrapper<T> wrapper) {
        Page<T> page = of(pageNum, pageSize);
        return (E) mapper.selectPage(page, wrapper);
    }
}
