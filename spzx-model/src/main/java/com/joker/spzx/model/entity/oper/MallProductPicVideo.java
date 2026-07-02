package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * <p>
 * 商品图片表
 * </p>
 *
 * @author joker
 * @since 2025-05-02 20:52:02
 */
@Getter
@Setter
@TableName("mall_product_picvideo")
@Schema(name = "MallProductPicvideo", description = "商品图片表")
public class MallProductPicVideo extends Model<MallProductPicVideo> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "商品Id")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "文件类型1图片2:视频")
    @TableField("file_type")
    private Integer fileType;

    @Schema(description = "文件名称")
    @TableField("file_name")
    private String fileName;

    @Schema(description = "文件地址")
    @TableField("file_url")
    private String fileUrl;

    @Schema(description = "刷单人Id")
    @TableField("person_id")
    private Long personId;

    @Schema(description = "拍图日期")
    @TableField("take_date")
    private String takeDate;

    @Schema(description = "状态0:未使用1:已使用")
    @TableField("state")
    private Integer state;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新人")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "创建时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
