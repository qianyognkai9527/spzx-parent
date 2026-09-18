package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_wordbank_batch")
public class KwWordbankBatch extends Model<KwWordbankBatch> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("name")
    private String name;

    @TableField("platform_type")
    private Integer platformType;

    @TableField("file_names")
    private String fileNames;

    @TableField("word_count")
    private Integer wordCount;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("remark")
    private String remark;
}
