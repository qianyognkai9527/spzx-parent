package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.List;

@Data
@TableName("category")
@Schema(name = "Category", description = "商品分类")
public class Category extends BaseEntity {

    @Schema(description = "分类名称")
    @TableField("name")
    private String name;

    @TableField("image_url")
    private String imageUrl;

    @Schema(description = "父分类id")
    @TableField("parent_id")
    private Long parentId;

    @Schema(description = "是否显示[0-不显示，1显示]")
    @TableField("status")
    private Byte status;

    @Schema(description = "排序")
    @TableField("order_num")
    private Integer orderNum;

    @Schema(description = "是否存在子节点")
    @TableField(exist = false)
    private Boolean hasChildren;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "子节点List集合")
    @TableField(exist = false)
    private List<Category> children;

}