package com.joker.spzx.model.entity.product;

import com.baomidou.mybatisplus.annotation.TableField;
import com.joker.spzx.model.entity.base.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "商品实体类")
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

    @Schema(description = "发货时长")
    @TableField("dispatch_time")
    private Integer dispatchTime;

    @Schema(description = "稳定状态：1-稳定，1-不太稳定，3-不稳定")
    @TableField("steady_status")
    private Integer steadyStatus;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;        // 审核信息

    @Schema(description = "更新人")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}