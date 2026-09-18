package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("kw_task_word")
public class KwTaskWord extends Model<KwTaskWord> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("keyword")
    private String keyword;

    @TableField("match_score")
    private Integer matchScore;

    @TableField("bank_score")
    private BigDecimal bankScore;

    @TableField("reason")
    private String reason;

    @TableField("picked")
    private Integer picked;
}
