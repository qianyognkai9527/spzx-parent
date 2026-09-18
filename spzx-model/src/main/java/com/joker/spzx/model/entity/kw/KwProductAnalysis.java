package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_product_analysis")
public class KwProductAnalysis extends Model<KwProductAnalysis> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("product_id")
    private Long productId;

    @TableField("platform_type")
    private Integer platformType;

    @TableField("title")
    private String title;

    @TableField("images")
    private String images;

    @TableField("ai_desc")
    private String aiDesc;

    @TableField("note")
    private String note;

    @TableField("create_time")
    private LocalDateTime createTime;
}
