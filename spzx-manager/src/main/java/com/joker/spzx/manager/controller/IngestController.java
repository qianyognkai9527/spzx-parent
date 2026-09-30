package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.ingest.IngestFreshnessService;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 采集契约只读接口：数据集新鲜度快照给任务进度页。
 * 写入路径不在此——Python 只写 ingest_batch/ingest_raw，洗数与告警由 IngestFreshnessTask 负责。
 */
@RestController
@RequestMapping("/admin/ingest")
public class IngestController {

    @Autowired
    private IngestFreshnessService ingestFreshnessService;

    @GetMapping("/datasets")
    public Result<List<IngestFreshnessService.Health>> datasets() {
        return Result.build(ingestFreshnessService.snapshot());
    }
}
