package com.joker.spzx.manager.service;

import cn.hutool.json.JSONObject;
import java.util.Map;

public interface FanqiePublishService {
    Map<String, Object> start();
    Map<String, Object> stop();
    Map<String, JSONObject> readState();

    /** 发布回执汇总：{published, pending, failed, updatedAt, fanqieMax} */
    Map<String, Object> summary();

    /** 把失败章节退回待发（清 publish_progress.json 的 failed 记录 + 状态文件置 pending） */
    Map<String, Object> requeue(int chapterNum);
}
