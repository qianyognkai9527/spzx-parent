package com.joker.spzx.model.entity.novel;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("novel_chapter")
public class NovelChapter extends BaseEntity {

    private Long novelId;

    private Integer chapterNum;

    private String title;

    private String content;

    private Integer wordCount;

    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime publishedAt;
}
