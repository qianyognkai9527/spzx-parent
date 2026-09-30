package com.joker.spzx.model.entity.promo;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 推广报表列名映射：CSV 原始列名 → 事实表字段。
 *
 * 这张表就是"还没见过真实导出文件"这个信息缺口的存放处——列名放这里当数据，
 * 而不是写死在解析器里，猜错的代价从"改代码重新发版"降成"改一行数据"。
 */
@Data
@Schema(name = "PromoImportMap", description = "推广报表列名映射")
@TableName("promo_import_map")
public class PromoImportMap {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "campaign=计划日报 item=明细日报")
    @TableField("report_level")
    private String reportLevel;

    @Schema(description = "CSV 原始列名")
    @TableField("source_column")
    private String sourceColumn;

    @Schema(description = "事实表字段名")
    @TableField("target_column")
    private String targetColumn;

    @Schema(description = "1=已用真实导出核对 0=预置待核对")
    private Integer verified;

    private Integer status;

    private String remark;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
