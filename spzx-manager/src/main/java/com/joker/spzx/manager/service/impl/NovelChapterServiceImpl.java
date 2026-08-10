package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.NovelChapterMapper;
import com.joker.spzx.manager.service.NovelChapterService;
import com.joker.spzx.model.entity.novel.NovelChapter;
import org.springframework.stereotype.Service;

@Service
public class NovelChapterServiceImpl extends ServiceImpl<NovelChapterMapper, NovelChapter> implements NovelChapterService {}
