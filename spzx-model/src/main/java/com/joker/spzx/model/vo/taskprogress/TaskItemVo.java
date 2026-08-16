package com.joker.spzx.model.vo.taskprogress;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "单个任务进度项")
public class TaskItemVo {

    @Schema(description = "任务key")
    private String key;

    @Schema(description = "任务名称")
    private String name;

    @Schema(description = "总数")
    private Integer total;

    @Schema(description = "已处理数")
    private Integer processed;

    @Schema(description = "成功数")
    private Integer saved;

    @Schema(description = "失败数")
    private Integer failed;

    @Schema(description = "进度百分比 0-100")
    private Integer progressPercent;

    @Schema(description = "状态: running/stopped/idle")
    private String status;

    @Schema(description = "最近日志摘要")
    private String lastLog;

    @Schema(description = "任务类别: scheduled/manual")
    private String category;

    @Schema(description = "平台标签: 淘宝/抖音/1688/其他")
    private java.util.List<String> tags;

    @Schema(description = "CDP端口 0=纯DB")
    private Integer port;

    @Schema(description = "只读展示的启动命令")
    private String launchCmd;

    @Schema(description = "调度表达式(仅定时任务)")
    private String schedule;

    @Schema(description = "下次运行时间(仅定时任务)")
    private String nextRun;
}
