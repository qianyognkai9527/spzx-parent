package com.joker.spzx.model.vo.taskprogress;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "任务进度看板总览")
public class TaskOverviewVo {

    @Schema(description = "任务进度项列表")
    private java.util.List<TaskItemVo> tasks;

    @Schema(description = "进程状态列表")
    private java.util.List<ProcessStatusVo> processes;
}
