package com.joker.spzx.manager.service;

import com.joker.spzx.model.entity.system.SysOperLog;
import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.bulk.BulkRequest;
import org.elasticsearch.action.bulk.BulkResponse;
import org.elasticsearch.action.index.IndexRequest;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class ElasticsearchLogService {

    private static final String INDEX_PREFIX = "sys_oper_log-";
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy.MM");

    @Autowired
    private RestHighLevelClient restHighLevelClient;

    public void saveOperLog(SysOperLog operLog) {
        try {
            Map<String, Object> doc = buildDoc(operLog);
            String indexName = INDEX_PREFIX + DATE_FORMAT.format(LocalDate.now());
            IndexRequest request = new IndexRequest(indexName).source(doc);
            restHighLevelClient.index(request, RequestOptions.DEFAULT);
        } catch (Exception e) {
            log.error("操作日志写入ES失败: {}", e.getMessage());
        }
    }

    public void saveOperLogBatch(List<SysOperLog> operLogs) {
        if (operLogs == null || operLogs.isEmpty()) {
            return;
        }
        try {
            BulkRequest bulkRequest = new BulkRequest();
            for (SysOperLog operLog : operLogs) {
                Map<String, Object> doc = buildDoc(operLog);
                String indexName = INDEX_PREFIX + DATE_FORMAT.format(LocalDate.now());
                bulkRequest.add(new IndexRequest(indexName).source(doc));
            }
            BulkResponse response = restHighLevelClient.bulk(bulkRequest, RequestOptions.DEFAULT);
            if (response.hasFailures()) {
                log.error("ES批量写入部分失败: {}", response.buildFailureMessage());
            }
        } catch (Exception e) {
            log.error("ES批量写入失败: {}", e.getMessage());
        }
    }

    private Map<String, Object> buildDoc(SysOperLog operLog) {
        Map<String, Object> doc = new HashMap<>();
        doc.put("title", operLog.getTitle());
        doc.put("method", operLog.getMethod());
        doc.put("requestMethod", operLog.getRequestMethod());
        doc.put("operatorType", operLog.getOperatorType());
        doc.put("operName", operLog.getOperName());
        doc.put("operUrl", operLog.getOperUrl());
        doc.put("operIp", operLog.getOperIp());
        doc.put("operParam", operLog.getOperParam());
        doc.put("jsonResult", operLog.getJsonResult());
        doc.put("status", operLog.getStatus());
        doc.put("errorMsg", operLog.getErrorMsg());
        doc.put("createTime", operLog.getCreateTime());
        doc.put("updateTime", operLog.getUpdateTime());
        doc.put("id", operLog.getId());
        doc.put("isDeleted", operLog.getIsDeleted());
        return doc;
    }
}