package com.joker.spzx.manager.service;

import lombok.extern.slf4j.Slf4j;
import org.elasticsearch.action.search.SearchRequest;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.client.RequestOptions;
import org.elasticsearch.client.RestHighLevelClient;
import org.elasticsearch.index.query.BoolQueryBuilder;
import org.elasticsearch.index.query.QueryBuilders;
import org.elasticsearch.search.SearchHit;
import org.elasticsearch.search.builder.SearchSourceBuilder;
import org.elasticsearch.search.sort.SortOrder;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.temporal.TemporalAdjusters;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class OperLogSearchService {

    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy.MM");

    @Autowired
    private RestHighLevelClient restHighLevelClient;

    public List<Map<String, Object>> search(String operName, String title, int page, int size) {
        String indexPattern = "sys_oper_log-*";

        BoolQueryBuilder boolQuery = QueryBuilders.boolQuery();
        if (operName != null && !operName.isEmpty()) {
            boolQuery.must(QueryBuilders.matchQuery("operName", operName));
        }
        if (title != null && !title.isEmpty()) {
            boolQuery.must(QueryBuilders.matchQuery("title", title));
        }

        SearchSourceBuilder sourceBuilder = new SearchSourceBuilder()
                .query(boolQuery)
                .from((page - 1) * size)
                .size(size)
                .sort("createTime", SortOrder.DESC);

        SearchRequest request = new SearchRequest(indexPattern).source(sourceBuilder);

        try {
            SearchResponse response = restHighLevelClient.search(request, RequestOptions.DEFAULT);
            List<Map<String, Object>> results = new ArrayList<>();
            for (SearchHit hit : response.getHits()) {
                results.add(hit.getSourceAsMap());
            }
            return results;
        } catch (Exception e) {
            log.error("搜索操作日志失败: {}", e.getMessage());
            return List.of();
        }
    }
}