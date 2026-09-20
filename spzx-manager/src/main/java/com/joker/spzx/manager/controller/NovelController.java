package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.FanqiePublishService;
import com.joker.spzx.manager.service.NovelChapterService;
import com.joker.spzx.manager.service.NovelService;
import com.joker.spzx.model.entity.novel.Novel;
import com.joker.spzx.model.entity.novel.NovelChapter;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Tag(name = "小说章节管理")
@RestController
@RequestMapping("/admin/novel")
public class NovelController {

    @Autowired
    private NovelService novelService;

    @Autowired
    private NovelChapterService novelChapterService;

    @Autowired
    private FanqiePublishService fanqiePublishService;

    // ===== 小说 =====

    @Operation(summary = "小说列表")
    @GetMapping("/list")
    public Result<List<Novel>> list() {
        return Result.build(novelService.list());
    }

    @Operation(summary = "小说详情(含大纲人设)")
    @GetMapping("/getById/{id}")
    public Result<Novel> getNovelById(@PathVariable Long id) {
        return Result.build(novelService.getById(id));
    }

    @Operation(summary = "更新小说(大纲/人设/标题等)")
    @PutMapping("/update")
    public Result update(@RequestBody Novel novel) {
        novelService.updateById(novel);
        return Result.build(null);
    }

    // ===== 章节 =====

    @Operation(summary = "章节分页")
    @GetMapping("/chapter/findByPage")
    public Result<Page<NovelChapter>> findByPage(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) Long novelId,
            @RequestParam(required = false) String title,
            @RequestParam(required = false) Integer status) {
        return Result.build(novelChapterService.findByPage(pageNum, pageSize, novelId, title, status));
    }

    @Operation(summary = "章节详情(含正文)")
    @GetMapping("/chapter/getById/{id}")
    public Result<NovelChapter> getById(@PathVariable Long id) {
        return Result.build(novelChapterService.getById(id));
    }

    @Operation(summary = "新增章节")
    @PostMapping("/chapter/save")
    public Result save(@RequestBody NovelChapter chapter) {
        if (chapter.getContent() != null) {
            chapter.setWordCount(chapter.getContent().length());
        }
        chapter.setIsModified(0);
        novelChapterService.save(chapter);
        return Result.build(null);
    }

    @Operation(summary = "修改章节")
    @PutMapping("/chapter/update")
    public Result update(@RequestBody NovelChapter chapter) {
        if (chapter.getContent() != null) {
            chapter.setWordCount(chapter.getContent().length());
        }
        chapter.setIsModified(1);
        novelChapterService.updateById(chapter);
        return Result.build(null);
    }

    @Operation(summary = "标记已发布")
    @PutMapping("/chapter/markPublished/{id}")
    public Result markPublished(@PathVariable Long id) {
        NovelChapter chapter = new NovelChapter();
        chapter.setId(id);
        chapter.setStatus(2);
        chapter.setPublishedAt(LocalDateTime.now());
        novelChapterService.updateById(chapter);
        return Result.build(null);
    }

    @Operation(summary = "一键启动番茄发布")
    @PostMapping("/publish/start")
    public Result<Map<String, Object>> startFanqiePublish() {
        return Result.build(fanqiePublishService.start(), ResultCodeEnum.SUCCESS);
    }

    @Operation(summary = "停止番茄发布")
    @PostMapping("/publish/stop")
    public Result<Map<String, Object>> stopFanqiePublish() {
        return Result.build(fanqiePublishService.stop(), ResultCodeEnum.SUCCESS);
    }

    @Operation(summary = "删除章节")
    @DeleteMapping("/chapter/remove/{id}")
    public Result remove(@PathVariable Long id) {
        novelChapterService.removeById(id);
        return Result.build(null);
    }
}
