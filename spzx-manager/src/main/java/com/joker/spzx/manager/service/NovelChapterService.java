package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.novel.NovelChapter;

public interface NovelChapterService extends IService<NovelChapter> {

    Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title, Integer status);
}
