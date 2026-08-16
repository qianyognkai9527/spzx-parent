package com.joker.spzx.manager.service;

import cn.hutool.json.JSONObject;
import java.util.Map;

public interface FanqiePublishService {
    Map<String, Object> start();
    Map<String, Object> stop();
    Map<String, JSONObject> readState();
}
