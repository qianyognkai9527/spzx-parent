package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.common.util.ShellUtil;
import com.joker.spzx.manager.service.FanqiePublishService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
public class FanqiePublishServiceImpl implements FanqiePublishService {

    @Value("${fanqie-publish.python-path:/Users/qyk9527/tb-auto/venv/bin/python}")
    private String pythonPath;

    @Value("${fanqie-publish.script-path:/Users/qyk9527/fanqie-publish/publish_fanqie.py}")
    private String scriptPath;

    @Value("${fanqie-publish.state-file:/Users/qyk9527/fanqie-publish/fanqie_publish_state.json}")
    private String stateFile;

    @Value("${fanqie-publish.log-file:/Users/qyk9527/fanqie-publish/fanqie-publish.log}")
    private String logFile;

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
            ShellUtil.ShellResult r = ShellUtil.run(
                    "nohup " + pythonPath + " " + scriptPath + " >> " + logFile + " 2>&1 & echo $!", 10_000);
            String newPid = r.output().trim();
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
            ShellUtil.ShellResult r = ShellUtil.run("pkill -f 'publish_fanqie.py' && echo killed || echo none", 10_000);
            boolean killed = r.output().trim().contains("killed");
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
            String content = Files.readString(Path.of(stateFile), StandardCharsets.UTF_8);
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
        ShellUtil.ShellResult r = ShellUtil.run(
                "ps aux | grep 'publish_fanqie.py' | grep -v grep | head -1 | awk '{print $2}'", 5_000);
        if (r.timedOut() || r.exitCode() != 0) {
            log.error("检查番茄发布进程失败: exit={}, timedOut={}, output={}",
                    r.exitCode(), r.timedOut(), r.output().trim());
            return null;
        }
        String out = r.output().trim();
        return out.isEmpty() ? null : out;
    }
}
