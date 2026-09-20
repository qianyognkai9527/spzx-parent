package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.NovelChapterMapper;
import com.joker.spzx.manager.service.FanqiePublishService;
import com.joker.spzx.manager.service.NovelChapterService;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.entity.novel.NovelChapter;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.Map;

@Service
public class NovelChapterServiceImpl extends ServiceImpl<NovelChapterMapper, NovelChapter> implements NovelChapterService {

    @Autowired
    private FanqiePublishService fanqiePublishService;

    @Override
    public Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title, Integer status) {
        LambdaQueryWrapper<NovelChapter> wrapper = new LambdaQueryWrapper<NovelChapter>()
                .eq(novelId != null, NovelChapter::getNovelId, novelId)
                .like(StringUtils.hasText(title), NovelChapter::getTitle, title)
                .eq(status != null, NovelChapter::getStatus, status)
                .eq(NovelChapter::getIsDeleted, 0)
                .orderByAsc(NovelChapter::getChapterNum);
        Page<NovelChapter> result = PageQueryUtil.page(this, pageNum, pageSize, wrapper);
        Map<String, JSONObject> fanqieState = fanqiePublishService.readState();
        if (!fanqieState.isEmpty()) {
            for (NovelChapter c : result.getRecords()) {
                JSONObject st = fanqieState.get(String.valueOf(c.getChapterNum()));
                if (st != null) {
                    c.setFanqieSchedule(st.getStr("schedule"));
                    c.setFanqieStatus(st.getStr("status"));
                    c.setFanqieError(st.getStr("error"));
                }
            }
        }
        return result;
    }
}
