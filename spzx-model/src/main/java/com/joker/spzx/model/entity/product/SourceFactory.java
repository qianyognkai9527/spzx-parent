package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * <p>
 * 爬虫工厂排行榜
 * </p>
 *
 * @author joker
 */
@Getter
@Setter
@TableName("source_factory")
@Schema(name = "SourceFactory", description = "爬虫工厂排行榜")
public class SourceFactory extends Model<SourceFactory> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "厂家名称")
    @TableField("factory_name")
    private String factoryName;

    @Schema(description = "诚信通年限")
    @TableField("trust_years")
    private Integer trustYears;

    @Schema(description = "商品数")
    @TableField("product_count")
    private Integer productCount;

    @Schema(description = "平均回头率%")
    @TableField("avg_repurchase_rate")
    private BigDecimal avgRepurchaseRate;

    @Schema(description = "总销量")
    @TableField("total_sales")
    private Integer totalSales;

    @Schema(description = "主类目")
    @TableField("category_name")
    private String categoryName;

    @Schema(description = "厂家链接(1688店铺)")
    @TableField("factory_url")
    private String factoryUrl;

    @Schema(description = "代表商品ID")
    @TableField("rep_offer_id")
    private String repOfferId;

    @Schema(description = "代表商品链接")
    @TableField("rep_product_url")
    private String repProductUrl;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "优质等级:A/B NULL=未达标")
    @TableField("quality_grade")
    private String qualityGrade;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "逻辑删除")
    @TableField("is_deleted")
    private Integer isDeleted;

}
