package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.NovelMapper;
import com.joker.spzx.manager.service.NovelService;
import com.joker.spzx.model.entity.novel.Novel;
import org.springframework.stereotype.Service;

@Service
public class NovelServiceImpl extends ServiceImpl<NovelMapper, Novel> implements NovelService {}
