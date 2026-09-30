package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.novel.NovelChapter;

public interface NovelChapterService extends IService<NovelChapter> {

    Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title, Integer status);

    /** fanqieStatus 非空时按番茄发布状态（published/pending/failed）过滤章号 */
    Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title,
                                  Integer status, String fanqieStatus);
}
