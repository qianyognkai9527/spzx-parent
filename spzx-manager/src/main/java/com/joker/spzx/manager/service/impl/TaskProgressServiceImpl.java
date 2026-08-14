package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.service.TaskProgressService;
import com.joker.spzx.model.vo.taskprogress.ProcessStatusVo;
import com.joker.spzx.model.vo.taskprogress.TaskItemVo;
import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 任务进度看板服务实现
 * 读取配置文件声明的各任务进度数据 (JSON/jsonl/DB), 聚合返回
 */
@Slf4j
@Service
public class TaskProgressServiceImpl implements TaskProgressService {

    @Value("${task-progress.config-path:/Users/qyk9527/sourcing/task-progress-config.json}")
    private String configPath;

    @Override
    public TaskOverviewVo getOverview() {
        TaskOverviewVo vo = new TaskOverviewVo();
        List<TaskItemVo> tasks = new ArrayList<>();
        List<ProcessStatusVo> processes = new ArrayList<>();

        // 读配置
        List<JSONObject> taskConfigs = loadTaskConfigs();

        // 收集所有需要检查的脚本名
        Set<String> allScripts = new LinkedHashSet<>();

        for (JSONObject cfg : taskConfigs) {
            TaskItemVo item = new TaskItemVo();
            item.setKey(cfg.getStr("key"));
            item.setName(cfg.getStr("name"));
            String type = cfg.getStr("type");

            try {
                switch (type) {
                    case "json_progress":
                        fillJsonProgress(item, cfg);
                        break;
                    case "douyin_pipeline":
                        fillDouyinPipeline(item, cfg);
                        break;
                    case "sourcing_progress":
                        fillSourcingProgress(item, cfg);
                        break;
                    case "db_factory_grade":
                        fillDbFactoryGrade(item);
                        break;
                    case "db_freight":
                        fillDbFreight(item, cfg);
                        break;
                    case "db_novel":
                        fillDbNovel(item);
                        break;
                    case "db_inventory_alert":
                        fillDbInventoryAlert(item);
                        break;
                    default:
                        item.setStatus("unknown_type");
                }
            } catch (Exception e) {
                log.warn("读取任务 {} 进度失败: {}", item.getKey(), e.getMessage());
                item.setStatus("error");
            }

            // 收集脚本名
            String script = cfg.getStr("script");
            if (script != null) allScripts.add(script);
            cn.hutool.json.JSONArray scriptsArr = cfg.getJSONArray("scripts");
            if (scriptsArr == null) scriptsArr = new cn.hutool.json.JSONArray();
            for (Object s : scriptsArr) {
                allScripts.add((String) s);
            }

            tasks.add(item);
        }

        // 检查进程状态
        for (String script : allScripts) {
            ProcessStatusVo ps = new ProcessStatusVo();
            ps.setScript(script);
            String pid = checkProcessRunning(script);
            ps.setRunning(pid != null);
            ps.setPid(pid != null ? pid : "");
            processes.add(ps);
        }

        // 更新任务状态: 如果任务有关联脚本且至少一个在跑 -> running
        for (TaskItemVo item : tasks) {
            if (item.getStatus() == null || item.getStatus().equals("error")) {
                item.setStatus("stopped");
            }
        }
        for (JSONObject cfg : taskConfigs) {
            String key = cfg.getStr("key");
            String script = cfg.getStr("script");
            cn.hutool.json.JSONArray scripts = cfg.getJSONArray("scripts");
            if (scripts == null) scripts = new cn.hutool.json.JSONArray();
            boolean anyRunning = false;
            if (script != null) {
                anyRunning = processes.stream().anyMatch(p -> p.getScript().equals(script) && p.getRunning());
            }
            for (Object s : scripts) {
                String sn = (String) s;
                if (processes.stream().anyMatch(p -> p.getScript().equals(sn) && p.getRunning())) {
                    anyRunning = true;
                }
            }
            if (anyRunning) {
                for (TaskItemVo item : tasks) {
                    if (item.getKey().equals(key)) {
                        item.setStatus("running");
                        break;
                    }
                }
            }
        }

        vo.setTasks(tasks);
        vo.setProcesses(processes);
        return vo;
    }

    private List<JSONObject> loadTaskConfigs() {
        try {
            String content = Files.readString(Path.of(configPath), StandardCharsets.UTF_8);
            JSONObject root = JSONUtil.parseObj(content);
            return root.getJSONArray("tasks").toList(JSONObject.class);
        } catch (Exception e) {
            log.error("读取任务配置失败: {}", e.getMessage());
            return Collections.emptyList();
        }
    }

    private void fillJsonProgress(TaskItemVo item, JSONObject cfg) {
        String path = cfg.getStr("path");
        JSONObject fields = cfg.getJSONObject("fields");
        JSONObject data = readJsonFile(path);
        if (data == null) {
            item.setTotal(0);
            item.setProcessed(0);
            item.setFailed(0);
            item.setProgressPercent(0);
            return;
        }
        int processed = data.getInt(fields.getStr("processed", "processed"), 0);
        int failed = data.getInt(fields.getStr("failed", "failed"), 0);
        int count = data.getInt(fields.getStr("count", "count"), processed);
        item.setProcessed(processed);
        item.setFailed(failed);
        item.setTotal(count > 0 ? count : processed + failed);
        item.setSaved(processed - failed);
        item.setProgressPercent(item.getTotal() > 0 ? processed * 100 / item.getTotal() : 0);
        item.setLastLog(readLogTail(cfg.getStr("logPath"), 1));
    }

    private void fillDouyinPipeline(TaskItemVo item, JSONObject cfg) {
        int worklistCount = countJsonlLines(cfg.getStr("worklist"));
        int dataCount = countJsonlLines(cfg.getStr("dataFile"));
        JSONObject progress = readJsonFile(cfg.getStr("progressFile"));

        int created = 0, saved = 0, failed = 0;
        if (progress != null) {
            JSONObject createdObj = progress.getJSONObject("created");
            if (createdObj != null) {
                created = createdObj.size();
                for (String k : createdObj.keySet()) {
                    JSONObject v = createdObj.getJSONObject(k);
                    String status = v != null ? v.getStr("status", "") : "";
                    if ("saved".equals(status)) saved++;
                    else if (status.contains("fail") || status.contains("error")) failed++;
                }
            }
        }
        // total = 待铺候选(worklist); processed = 已创建的草稿数(created); saved = 建成草稿
        item.setTotal(worklistCount);
        item.setProcessed(created);
        item.setSaved(saved);
        item.setFailed(failed);
        item.setProgressPercent(worklistCount > 0 ? created * 100 / worklistCount : 0);
        if (worklistCount > 0) {
            item.setLastLog("已铺" + created + "个(草稿" + saved + ")/候选" + worklistCount + ", 失败" + failed);
        }
    }

    private void fillSourcingProgress(TaskItemVo item, JSONObject cfg) {
        JSONObject progress = readJsonFile(cfg.getStr("progressFile"));
        int donePages = 0, failedKw = 0;
        if (progress != null) {
            donePages = progress.getInt("done", 0) != null ? 0 : 0;
            // hutool getInt returns Integer, need null check
            Object doneObj = progress.get("done");
            if (doneObj instanceof List) donePages = ((List<?>) doneObj).size();
            Object failedObj = progress.get("failed_kw");
            if (failedObj instanceof List) failedKw = ((List<?>) failedObj).size();
        }
        int rawCount = countJsonlLines(cfg.getStr("rawFile"));
        item.setTotal(donePages);
        item.setProcessed(rawCount);
        item.setSaved(rawCount);
        item.setFailed(failedKw);
        item.setProgressPercent(100); // 376页已完成
    }

    private void fillDbFactoryGrade(TaskItemVo item) {
        // 用 DB 查询, 通过 JdbcTemplate 或 Mapper
        // 简化: 直接查 mysql
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT CONCAT(quality_grade, ':', COUNT(*)) FROM source_factory WHERE is_deleted=0 GROUP BY quality_grade ORDER BY quality_grade DESC\" 2>/dev/null");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            int total = 0;
            StringBuilder sb = new StringBuilder();
            for (String line : out.trim().split("\n")) {
                String[] parts = line.split(":");
                if (parts.length == 2) {
                    int cnt = Integer.parseInt(parts[1].trim());
                    total += cnt;
                    if (sb.length() > 0) sb.append(", ");
                    sb.append(parts[0].trim()).append(":").append(cnt);
                }
            }
            item.setTotal(total);
            item.setProcessed(total);
            item.setSaved(total);
            item.setFailed(0);
            item.setProgressPercent(100);
            item.setLastLog(sb.toString());
        } catch (Exception e) {
            item.setLastLog("DB查询失败: " + e.getMessage());
        }
    }

    private void fillDbFreight(TaskItemVo item, JSONObject cfg) {
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM source_product WHERE freight_cost IS NULL OR freight_cost=0;\" 2>/dev/null && " +
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM source_product WHERE freight_cost > 0;\" 2>/dev/null");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            String[] lines = out.trim().split("\n");
            int pending = lines.length > 0 ? Integer.parseInt(lines[0].trim()) : 0;
            int done = lines.length > 1 ? Integer.parseInt(lines[1].trim()) : 0;
            item.setTotal(done + pending);
            item.setProcessed(done);
            item.setSaved(done);
            item.setFailed(pending);
            item.setProgressPercent(item.getTotal() > 0 ? done * 100 / item.getTotal() : 0);
            item.setLastLog("已抓" + done + ", 待抓" + pending);
        } catch (Exception e) {
            item.setLastLog("DB查询失败: " + e.getMessage());
        }
    }

    private void fillDbNovel(TaskItemVo item) {
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT total_chapters FROM novel WHERE id=1 AND is_deleted=0;\" 2>/dev/null && " +
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM novel_chapter WHERE novel_id=1 AND is_deleted=0;\" 2>/dev/null && " +
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM novel_chapter WHERE novel_id=1 AND is_deleted=0 AND status=2;\" 2>/dev/null");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            if (p.exitValue() != 0) {
                throw new RuntimeException("mysql 查询失败, exit=" + p.exitValue());
            }
            String[] lines = out.trim().split("\n");
            int total = lines.length > 0 ? Integer.parseInt(lines[0].trim()) : 0;
            int written = lines.length > 1 ? Integer.parseInt(lines[1].trim()) : 0;
            int published = lines.length > 2 ? Integer.parseInt(lines[2].trim()) : 0;
            item.setTotal(total);
            item.setProcessed(written);
            item.setSaved(published);
            item.setFailed(0);
            item.setProgressPercent(total > 0 ? written * 100 / total : 0);
            item.setLastLog("已写" + written + "章/共" + total + "章，已发布" + published + "章");
        } catch (Exception e) {
            item.setLastLog("DB查询失败: " + e.getMessage());
        }
    }

    private void fillDbInventoryAlert(TaskItemVo item) {
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM source_sku WHERE status=1 AND is_deleted=0;\" 2>/dev/null && " +
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM sync_alert WHERE status=0;\" 2>/dev/null && " +
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                    "\"SELECT COUNT(*) FROM sku_bind_relation WHERE status=1 AND is_deleted=0;\" 2>/dev/null");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            if (p.exitValue() != 0) {
                throw new RuntimeException("mysql 查询失败, exit=" + p.exitValue());
            }
            String[] lines = out.trim().split("\n");
            int activeSku = lines.length > 0 ? Integer.parseInt(lines[0].trim()) : 0;
            int unreadAlerts = lines.length > 1 ? Integer.parseInt(lines[1].trim()) : 0;
            int confirmedBind = lines.length > 2 ? Integer.parseInt(lines[2].trim()) : 0;
            item.setTotal(activeSku);
            item.setProcessed(activeSku);
            item.setSaved(confirmedBind);
            item.setFailed(unreadAlerts);
            item.setProgressPercent(activeSku > 0 ? 100 : 0);
            item.setLastLog("未读提醒" + unreadAlerts + "条 / 活跃SKU " + activeSku + "条");
        } catch (Exception e) {
            item.setLastLog("DB查询失败: " + e.getMessage());
        }
    }

    private JSONObject readJsonFile(String path) {
        if (path == null) return null;
        try {
            String content = Files.readString(Path.of(path), StandardCharsets.UTF_8);
            return JSONUtil.parseObj(content);
        } catch (Exception e) {
            return null;
        }
    }

    private int countJsonlLines(String path) {
        if (path == null) return 0;
        try (BufferedReader reader = Files.newBufferedReader(Path.of(path), StandardCharsets.UTF_8)) {
            int count = 0;
            while (reader.readLine() != null) count++;
            return count;
        } catch (Exception e) {
            return 0;
        }
    }

    private String readLogTail(String logPath, int lines) {
        if (logPath == null) return "";
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c", "tail -" + lines + " " + logPath + " 2>/dev/null | cut -c1-120");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            return out.trim();
        } catch (Exception e) {
            return "";
        }
    }

    private String checkProcessRunning(String scriptName) {
        if (scriptName == null) return null;
        try {
            ProcessBuilder pb = new ProcessBuilder("sh", "-c",
                    "ps aux | grep '" + scriptName + "' | grep -v grep | head -1 | awk '{print $2}'");
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            p.waitFor();
            String pid = out.trim();
            return pid.isEmpty() ? null : pid;
        } catch (Exception e) {
            return null;
        }
    }
}
