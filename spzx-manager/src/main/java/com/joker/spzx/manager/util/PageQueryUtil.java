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

    private PageQueryUtil() {
    }

    /**
     * IService 分页查询（wrapper 可为 null，等价于无条件的 page(page)）；
     * E 由调用方赋值目标推断（IPage 或 Page），运行时对象即为本次构造的 Page，强转安全
     */
    @SuppressWarnings("unchecked")
    public static <T, E extends IPage<T>> E page(IService<T> service, Integer pageNum, Integer pageSize, Wrapper<T> wrapper) {
        Page<T> page = new Page<>(pageNum, pageSize);
        return (E) service.page(page, wrapper);
    }

    /**
     * BaseMapper 分页查询（同上）
     */
    @SuppressWarnings("unchecked")
    public static <T, E extends IPage<T>> E page(BaseMapper<T> mapper, Integer pageNum, Integer pageSize, Wrapper<T> wrapper) {
        Page<T> page = new Page<>(pageNum, pageSize);
        return (E) mapper.selectPage(page, wrapper);
    }
}
