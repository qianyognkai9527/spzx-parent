package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.service.FanqiePublishService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class FanqiePublishServiceImpl implements FanqiePublishService {

    private static final String PYTHON = "/Users/qyk9527/tb-auto/venv/bin/python";
    private static final String SCRIPT = "/Users/qyk9527/fanqie-publish/publish_fanqie.py";
    private static final String STATE_FILE = "/Users/qyk9527/fanqie-publish/fanqie_publish_state.json";
    private static final String LOG_FILE = "/Users/qyk9527/fanqie-publish/fanqie-publish.log";

    @Override
    public Map<String, Object> start() {
        Map<String, Object> res = new HashMap<>();
        String pid = checkRunning();
        if (pid != null) {
            res.put("ok", false);
            res.put("message", "发布任务已在运行 (PID " + pid + ")");
            return res;
        }
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "nohup " + PYTHON + " " + SCRIPT + " >> " + LOG_FILE + " 2>&1 & echo $!");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            String newPid = out.trim();
            res.put("ok", true);
            res.put("message", newPid.isEmpty() ? "已启动发布任务" : "已启动发布任务 (PID " + newPid + ")");
        } catch (Exception e) {
            log.error("启动番茄发布失败", e);
            res.put("ok", false);
            res.put("message", "启动失败: " + e.getMessage());
        }
        return res;
    }

    @Override
    public Map<String, Object> stop() {
        Map<String, Object> res = new HashMap<>();
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c", "pkill -f 'publish_fanqie.py' && echo killed || echo none");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            boolean killed = out.trim().contains("killed");
            res.put("ok", killed);
            res.put("message", killed ? "已停止发布任务" : "未发现运行中的发布任务");
        } catch (Exception e) {
            log.error("停止番茄发布失败", e);
            res.put("ok", false);
            res.put("message", "停止失败: " + e.getMessage());
        }
        return res;
    }

    @Override
    public Map<String, JSONObject> readState() {
        try {
            String content = Files.readString(Path.of(STATE_FILE), StandardCharsets.UTF_8);
            JSONObject root = JSONUtil.parseObj(content);
            JSONObject chapters = root.getJSONObject("chapters");
            Map<String, JSONObject> result = new HashMap<>();
            if (chapters != null) {
                for (String k : chapters.keySet()) {
                    result.put(k, chapters.getJSONObject(k));
                }
            }
            return result;
        } catch (Exception e) {
            log.warn("读取番茄发布状态失败: {}", e.getMessage());
            return Collections.emptyMap();
        }
    }

    private String checkRunning() {
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "ps aux | grep 'publish_fanqie.py' | grep -v grep | head -1 | awk '{print $2}'");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            return out.trim().isEmpty() ? null : out.trim();
        } catch (Exception e) {
            return null;
        }
    }
}
