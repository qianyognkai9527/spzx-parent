package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("kw_wordbank_item")
public class KwWordbankItem extends Model<KwWordbankItem> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("batch_id")
    private Long batchId;

    @TableField("keyword")
    private String keyword;

    @TableField("search_popularity")
    private Integer searchPopularity;

    @TableField("click_rate")
    private BigDecimal clickRate;

    @TableField("conv_rate")
    private BigDecimal convRate;

    @TableField("buyer_count")
    private Integer buyerCount;

    @TableField("score")
    private BigDecimal score;
}
