package com.joker.spzx.model.vo.taskprogress;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "进程运行状态")
public class ProcessStatusVo {

    @Schema(description = "脚本名称")
    private String script;

    @Schema(description = "是否运行中")
    private Boolean running;

    @Schema(description = "PID")
    private String pid;
}
