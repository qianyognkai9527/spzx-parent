package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("source_product")
@Schema(description = "货源商品实体类")
public class Product extends BaseEntity {

    @Schema(description = "货源商品名称")
    @TableField("source_product_name")
    private String sourceProductName;

    @Schema(description = "货源厂商Id")
    @TableField("product_factory_id")
    private Long productFactoryId;

    @Schema(description = "货源商品Id")
    @TableField("source_product_code")
    private String sourceProductCode;

    @Schema(description = "货源商品链接地址")
    @TableField("source_product_url")
    private String sourceProductUrl;

    @Schema(description = "头图链接地址")
    @TableField("head_img_url")
    private String headImgUrl;

    @Schema(description = "发货物流公司")
    @TableField("logistics_name")
    private String logisticsName;

    @Schema(description = "运费")
    @TableField("freight_cost")
    private BigDecimal freightCost;

    @Schema(description = "货源价格")
    @TableField("source_price")
    private BigDecimal sourcePrice;

    @Schema(description = "发货时长")
    @TableField("dispatch_time")
    private Integer dispatchTime;

    @Schema(description = "稳定状态：1-稳定，1-不太稳定，3-不稳定")
    @TableField("steady_status")
    private Integer steadyStatus;

    @Schema(description = "带图评价数量")
    @TableField("eval_with_image_count")
    private Integer evalWithImageCount;

    @Schema(description = "供应商名称(爬虫)")
    @TableField("supplier_name")
    private String supplierName;

    @Schema(description = "回头率%(爬虫)")
    @TableField("repurchase_rate")
    private BigDecimal repurchaseRate;

    @Schema(description = "全网销量(爬虫)")
    @TableField("sales_count")
    private Integer salesCount;

    @Schema(description = "类目(爬虫)")
    @TableField("category_name")
    private String categoryName;

    @Schema(description = "关键词(爬虫)")
    @TableField("keyword")
    private String keyword;

    @Schema(description = "诚信通年限(爬虫)")
    @TableField("trust_years")
    private Integer trustYears;

    @Schema(description = "关联source_factory(爬虫厂家)")
    @TableField("source_factory_id")
    private Long sourceFactoryId;

    @Schema(description = "采集时间")
    @TableField("crawl_time")
    private java.time.LocalDateTime crawlTime;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;        // 审核信息

    @Schema(description = "更新人")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Schema(description = "数据来源:1=1688搜索候选 2=ISV已铺货")
    @TableField("data_source")
    private Integer dataSource;

    @Schema(description = "优质等级:A/B/C NULL=未达标")
    @TableField("quality_grade")
    private String qualityGrade;

}