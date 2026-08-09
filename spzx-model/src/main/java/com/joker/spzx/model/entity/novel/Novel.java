package com.joker.spzx.model.entity.novel;

import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("novel")
public class Novel extends BaseEntity {

    private String title;

    private String genre;

    private String description;

    private String outline;

    private String characters;

    private Integer totalChapters;

    private Integer status;
}
