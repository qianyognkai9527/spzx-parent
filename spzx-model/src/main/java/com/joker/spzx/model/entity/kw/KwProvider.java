package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("kw_provider")
public class KwProvider extends Model<KwProvider> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("name")
    private String name;

    @TableField("base_url")
    private String baseUrl;

    @TableField("api_key")
    private String apiKey;

    @TableField("vision_model")
    private String visionModel;

    @TableField("text_model")
    private String textModel;

    @TableField("image_model")
    private String imageModel;

    @TableField("video_model")
    private String videoModel;

    @TableField("video_price")
    private BigDecimal videoPrice;

    @TableField("max_tokens")
    private Integer maxTokens;

    @TableField("extra_body")
    private String extraBody;

    @TableField("status")
    private Integer status;

    @TableField("remark")
    private String remark;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
