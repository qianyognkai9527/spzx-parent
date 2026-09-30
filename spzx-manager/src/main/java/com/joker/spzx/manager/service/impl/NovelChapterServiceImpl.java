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

import java.util.List;
import java.util.Map;

@Service
public class NovelChapterServiceImpl extends ServiceImpl<NovelChapterMapper, NovelChapter> implements NovelChapterService {

    @Autowired
    private FanqiePublishService fanqiePublishService;

    @Override
    public Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title, Integer status) {
        return findByPage(pageNum, pageSize, novelId, title, status, null);
    }

    @Override
    public Page<NovelChapter> findByPage(Integer pageNum, Integer pageSize, Long novelId, String title,
                                         Integer status, String fanqieStatus) {
        Map<String, JSONObject> fanqieState = fanqiePublishService.readState();
        LambdaQueryWrapper<NovelChapter> wrapper = new LambdaQueryWrapper<NovelChapter>()
                .eq(novelId != null, NovelChapter::getNovelId, novelId)
                .like(StringUtils.hasText(title), NovelChapter::getTitle, title)
                .eq(status != null, NovelChapter::getStatus, status)
                .orderByAsc(NovelChapter::getChapterNum);
        if (StringUtils.hasText(fanqieStatus)) {
            // 发布状态只活在脚本写的状态文件里，无法进 SQL：先取命中章号再 in 过滤。
            // 状态文件是 Python 直接写的外部产物，键可能是非章号、值可能是 null，
            // 这里不兜住就会让整个章节列表 500。
            List<Integer> nums = fanqieState.entrySet().stream()
                    .filter(e -> e.getValue() != null
                            && e.getKey().matches("\\d+")
                            && fanqieStatus.equals(e.getValue().getStr("status")))
                    .map(e -> Integer.valueOf(e.getKey()))
                    .toList();
            if (nums.isEmpty()) {
                return new Page<>(pageNum, pageSize, 0);
            }
            wrapper.in(NovelChapter::getChapterNum, nums);
        }
        Page<NovelChapter> result = PageQueryUtil.page(this, pageNum, pageSize, wrapper);
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
