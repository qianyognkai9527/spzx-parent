package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.common.util.ShellUtil;
import com.joker.spzx.manager.service.TaskProgressService;
import com.joker.spzx.model.vo.taskprogress.ChromeStatusVo;
import com.joker.spzx.model.vo.taskprogress.ProcessStatusVo;
import com.joker.spzx.model.vo.taskprogress.TaskItemVo;
import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
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

    /** 清理标签页时保留的关键 URL 前缀 (登录页/主页/工作页) */
    private static final List<String> KEEP_URL_PREFIXES = List.of(
            "myseller.taobao.com",
            "item.upload.taobao.com",
            "s.1688.com",
            "ufuwu.1688.com",
            "fxg.jinritemai.com",
            "detail.1688.com"
    );

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
            // 透传新配置字段
            item.setCategory(cfg.getStr("category", "manual"));
            item.setTags(toStringList(cfg.getJSONArray("tags")));
            item.setPort(cfg.getInt("port", 0));
            item.setLaunchCmd(cfg.getStr("launchCmd"));
            item.setSchedule(cfg.getStr("schedule"));
            item.setNextRun(cfg.getStr("nextRun"));
            String type = cfg.getStr("type");

            try {
                switch (type) {
                    case "json_progress":
                        fillJsonProgress(item, cfg);
                        break;
                    case "list_progress":
                        fillListProgress(item, cfg);
                        break;
                    case "map_progress":
                        fillMapProgress(item, cfg);
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
                    case "fanqie_publish":
                        fillFanqiePublish(item, cfg);
                        break;
                    case "db_inventory_alert":
                        fillDbInventoryAlert(item);
                        break;
                    case "process_only":
                        fillProcessOnly(item, cfg);
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
            JSONArray scriptsArr = cfg.getJSONArray("scripts");
            if (scriptsArr == null) scriptsArr = new JSONArray();
            for (Object s : scriptsArr) {
                allScripts.add((String) s);
            }

            tasks.add(item);
        }

        // 检查进程状态 (单次 ps 快照, 避免 30+ 次子进程)
        Map<String, String> procMap = processSnapshot();
        for (String script : allScripts) {
            ProcessStatusVo ps = new ProcessStatusVo();
            ps.setScript(script);
            String pid = procMap.get(script);
            ps.setRunning(pid != null);
            ps.setPid(pid != null ? pid : "");
            processes.add(ps);
        }

        // 更新任务状态: 如果任务有关联脚本且至少一个在跑 -> running
        for (TaskItemVo item : tasks) {
            if (item.getStatus() == null || item.getStatus().equals("error") || item.getStatus().equals("unknown_type")) {
                item.setStatus("stopped");
            }
        }
        for (JSONObject cfg : taskConfigs) {
            String key = cfg.getStr("key");
            String script = cfg.getStr("script");
            JSONArray scripts = cfg.getJSONArray("scripts");
            if (scripts == null) scripts = new JSONArray();
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
        vo.setChromeStats(collectChromeStats());
        return vo;
    }

    @Override
    public int closeTabs(int port) {
        int closed = 0;
        try {
            // 1. 查询目标列表
            URL jsonUrl = new URL("http://127.0.0.1:" + port + "/json");
            HttpURLConnection conn = (HttpURLConnection) jsonUrl.openConnection();
            conn.setConnectTimeout(2000);
            conn.setReadTimeout(3000);
            String body;
            try (InputStream in = conn.getInputStream()) {
                body = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
            JSONArray targets = JSONUtil.parseArray(body);

            // 2. 智能保留: item.upload 仅在铺货(auto_list)运行时保留, 否则属残留一并清理
            List<String> keepPrefixes = new ArrayList<>(KEEP_URL_PREFIXES);
            if (!isScriptRunning("auto_list.py")) {
                keepPrefixes.remove("item.upload.taobao.com");
            }

            // 3. 关闭非保留 URL 的 page 类型标签
            List<String> toClose = new ArrayList<>();
            for (Object o : targets) {
                JSONObject t = (JSONObject) o;
                String type = t.getStr("type");
                String url = t.getStr("url", "");
                if (!"page".equals(type)) continue;
                if (url.isEmpty() || url.startsWith("about:") || url.startsWith("chrome://")) {
                    toClose.add(t.getStr("id"));
                    continue;
                }
                boolean keep = false;
                for (String prefix : keepPrefixes) {
                    if (url.contains(prefix)) {
                        keep = true;
                        break;
                    }
                }
                if (!keep) toClose.add(t.getStr("id"));
            }

            // 4. 逐个关闭
            for (String id : toClose) {
                try {
                    URL closeUrl = new URL("http://127.0.0.1:" + port + "/json/close/" + id);
                    HttpURLConnection c2 = (HttpURLConnection) closeUrl.openConnection();
                    c2.setConnectTimeout(1500);
                    c2.setReadTimeout(1500);
                    try (InputStream in = c2.getInputStream()) {
                        in.readAllBytes();
                    }
                    closed++;
                } catch (Exception e) {
                    log.warn("关闭标签 {} 失败: {}", id, e.getMessage());
                }
            }
        } catch (Exception e) {
            log.warn("清理端口 {} 标签页失败: {}", port, e.getMessage());
        }
        return closed;
    }

    // ==================== Chrome 资源统计 ====================

    private List<ChromeStatusVo> collectChromeStats() {
        List<ChromeStatusVo> stats = new ArrayList<>();
        stats.add(chromeStat(9222));
        stats.add(chromeStat(9223));
        return stats;
    }

    private ChromeStatusVo chromeStat(int port) {
        ChromeStatusVo vo = new ChromeStatusVo();
        vo.setPort(port);
        // 1. Chrome 主进程是否存活
        boolean running = isPortAlive(port);
        vo.setRunning(running);
        if (!running) {
            vo.setTabs(0);
            vo.setRssMB(0);
            vo.setCpuPercent(0.0);
            vo.setDesc("Chrome 未运行");
            return vo;
        }
        // 2. 标签页数
        int tabs = countTabs(port);
        vo.setTabs(tabs);
        // 3. RSS/CPU 聚合
        long[] rssCpu = rssCpuForPort(port);
        vo.setRssMB((int) (rssCpu[0] / 1024));
        vo.setCpuPercent(rssCpu[1] / 100.0);
        vo.setDesc(tabs + " 个标签页");
        return vo;
    }

    private boolean isPortAlive(int port) {
        try {
            URL url = new URL("http://127.0.0.1:" + port + "/json/version");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(1500);
            int code = conn.getResponseCode();
            try (InputStream in = conn.getInputStream()) {
                in.readAllBytes();
            }
            return code == 200;
        } catch (Exception e) {
            return false;
        }
    }

    private int countTabs(int port) {
        try {
            URL url = new URL("http://127.0.0.1:" + port + "/json");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(2000);
            String body;
            try (InputStream in = conn.getInputStream()) {
                body = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
            return JSONUtil.parseArray(body).size();
        } catch (Exception e) {
            return 0;
        }
    }

    /** 返回 [rssKB, cpuHundredths] */
    private long[] rssCpuForPort(int port) {
        long rss = 0;
        long cpu = 0;
        int count = 0;
        try {
            ShellUtil.ShellResult r = ShellUtil.run(
                    "ps -Ao rss=,pcpu=,command | grep 'remote-debugging-port=" + port + "' | grep -v grep", 5_000);
            String out = r.output();
            for (String line : out.split("\n")) {
                if (line.trim().isEmpty()) continue;
                String[] parts = line.trim().split("\\s+", 3);
                if (parts.length >= 2) {
                    try {
                        rss += Long.parseLong(parts[0].trim());
                        cpu += (long) (Double.parseDouble(parts[1].trim()) * 100);
                        count++;
                    } catch (NumberFormatException ignored) {
                        log.warn("端口 {} 资源行解析失败: {}", port, line, ignored);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("统计端口 {} 资源失败: {}", port, e.getMessage());
        }
        return new long[]{rss, cpu};
    }

    // ==================== 配置读取 ====================

    private List<JSONObject> loadTaskConfigs() {
        try {
            String content = Files.readString(Path.of(configPath), StandardCharsets.UTF_8);
            JSONObject root = JSONUtil.parseObj(content);
            return root.getJSONArray("tasks").toList(JSONObject.class);
        } catch (Exception e) {
            log.error("读取任务配置失败", e);
            return Collections.emptyList();
        }
    }

    // ==================== 进度读取器 ====================

    private List<String> toStringList(JSONArray arr) {
        List<String> out = new ArrayList<>();
        if (arr == null) return out;
        for (Object o : arr) out.add(String.valueOf(o));
        return out;
    }

    /** 读取 JSON 进度字段, 兼容 int 与数组 */
    private int jsonIntOrLen(JSONObject data, String key) {
        Object v = data.get(key);
        if (v == null) return 0;
        if (v instanceof JSONArray arr) return arr.size();
        if (v instanceof List list) return list.size();
        return data.getInt(key, 0);
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
        int processed = jsonIntOrLen(data, fields.getStr("processed", "processed"));
        int failed = jsonIntOrLen(data, fields.getStr("failed", "failed"));
        int count = jsonIntOrLen(data, fields.getStr("count", "count"));
        if (count == 0 && fields.containsKey("done")) {
            count = jsonIntOrLen(data, fields.getStr("done"));
        }
        item.setProcessed(processed);
        item.setFailed(failed);
        item.setTotal(count > 0 ? count : processed + failed);
        item.setSaved(processed - failed > 0 ? processed - failed : 0);
        item.setProgressPercent(item.getTotal() > 0 ? processed * 100 / item.getTotal() : 0);
        item.setLastLog(readLogTail(cfg.getStr("logPath"), 1));
    }

    private void fillListProgress(TaskItemVo item, JSONObject cfg) {
        JSONObject data = readJsonFile(cfg.getStr("path"));
        int processed = 0, failed = 0;
        if (data != null) {
            processed = jsonIntOrLen(data, cfg.getStr("doneKey", "done"));
            failed = jsonIntOrLen(data, cfg.getStr("failedKey", "failed"));
        }
        item.setProcessed(processed);
        item.setFailed(failed);
        item.setSaved(processed - failed > 0 ? processed - failed : 0);
        item.setTotal(processed + failed);
        item.setProgressPercent(item.getTotal() > 0 ? processed * 100 / item.getTotal() : 0);
        item.setLastLog(readLogTail(cfg.getStr("logPath"), 1));
    }

    private void fillMapProgress(TaskItemVo item, JSONObject cfg) {
        JSONObject data = readJsonFile(cfg.getStr("path"));
        JSONObject map = data;
        String mapKey = cfg.getStr("mapKey");
        if (data != null && mapKey != null) map = data.getJSONObject(mapKey);
        int saved = 0, failed = 0;
        if (map != null) {
            for (String k : map.keySet()) {
                JSONObject v = map.getJSONObject(k);
                String status = v != null ? v.getStr("status", "") : "";
                if ("saved".equals(status)) saved++;
                else if (status.contains("fail") || status.contains("error") || status.contains("risk")) failed++;
            }
        }
        int total = map != null ? map.size() : 0;
        item.setTotal(total);
        item.setProcessed(total);
        item.setSaved(saved);
        item.setFailed(failed);
        item.setProgressPercent(total > 0 ? 100 : 0);
        if (total > 0) item.setLastLog("已处理" + total + ", 成功" + saved + ", 失败" + failed);
    }

    private void fillProcessOnly(TaskItemVo item, JSONObject cfg) {
        item.setProcessed(0);
        item.setTotal(0);
        item.setSaved(0);
        item.setFailed(0);
        item.setProgressPercent(0);
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
            Object doneObj = progress.get("done");
            if (doneObj instanceof List) donePages = ((List<?>) doneObj).size();
            Object failedObj = progress.get("failed_kw");
            if (failedObj instanceof List) failedKw = ((List<?>) failedObj).size();
        }
        int rawCount = countJsonlLines(cfg.getStr("rawFile"));
        item.setTotal(rawCount);
        item.setProcessed(rawCount);
        item.setSaved(rawCount);
        item.setFailed(failedKw);
        item.setProgressPercent(100);
        item.setLastLog("已完成 " + donePages + " 页 / 已采 " + rawCount + " 条, 失败关键词 " + failedKw);
    }

    private void fillDbFactoryGrade(TaskItemVo item) {
        // 用 DB 查询, 通过 JdbcTemplate 或 Mapper
        // 简化: 直接查 mysql
        try {
            ShellUtil.ShellResult r = ShellUtil.run(
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT CONCAT(quality_grade, ':', COUNT(*)) FROM source_factory WHERE is_deleted=0 GROUP BY quality_grade ORDER BY quality_grade DESC\" 2>/dev/null",
                    10_000);
            String out = r.output();
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
            ShellUtil.ShellResult r = ShellUtil.run(
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM source_product WHERE freight_cost IS NULL OR freight_cost=0;\" 2>/dev/null && " +
                            "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM source_product WHERE freight_cost > 0;\" 2>/dev/null",
                    10_000);
            String out = r.output();
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
            ShellUtil.ShellResult r = ShellUtil.run(
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT total_chapters FROM novel WHERE id=1 AND is_deleted=0;\" 2>/dev/null && " +
                            "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM novel_chapter WHERE novel_id=1 AND is_deleted=0;\" 2>/dev/null && " +
                            "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM novel_chapter WHERE novel_id=1 AND is_deleted=0 AND status=2;\" 2>/dev/null",
                    10_000);
            if (r.exitCode() != 0) {
                throw new RuntimeException("mysql 查询失败, exit=" + r.exitCode());
            }
            String out = r.output();
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

    private void fillFanqiePublish(TaskItemVo item, JSONObject cfg) {
        JSONObject state = readJsonFile(cfg.getStr("path"));
        int published = 0, pending = 0, failed = 0;
        if (state != null) {
            JSONObject chapters = state.getJSONObject("chapters");
            if (chapters != null) {
                for (String k : chapters.keySet()) {
                    JSONObject c = chapters.getJSONObject(k);
                    String st = c != null ? c.getStr("status", "") : "";
                    if ("published".equals(st)) published++;
                    else if ("failed".equals(st)) failed++;
                    else pending++;
                }
            }
        }
        int total = published + pending + failed;
        item.setTotal(total);
        item.setProcessed(published + failed);
        item.setSaved(published);
        item.setFailed(failed);
        item.setProgressPercent(total > 0 ? published * 100 / total : 0);
        String updatedAt = state != null ? state.getStr("updatedAt", "") : "";
        String tail = readLogTail(cfg.getStr("logPath"), 3);
        StringBuilder sb = new StringBuilder("已发布").append(published).append("/").append(total)
                .append("章, 待发").append(pending).append(", 失败").append(failed);
        if (!updatedAt.isEmpty()) sb.append(" | 更新于 ").append(updatedAt);
        if (!tail.isEmpty()) sb.append(" | ").append(tail);
        item.setLastLog(sb.toString());
    }

    private void fillDbInventoryAlert(TaskItemVo item) {
        try {
            ShellUtil.ShellResult r = ShellUtil.run(
                    "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM source_sku WHERE status=1 AND is_deleted=0;\" 2>/dev/null && " +
                            "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM sync_alert WHERE status=0;\" 2>/dev/null && " +
                            "/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -N -e " +
                            "\"SELECT COUNT(*) FROM sku_bind_relation WHERE status=1 AND is_deleted=0;\" 2>/dev/null",
                    10_000);
            if (r.exitCode() != 0) {
                throw new RuntimeException("mysql 查询失败, exit=" + r.exitCode());
            }
            String out = r.output();
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

    // ==================== 工具方法 ====================

    private JSONObject readJsonFile(String path) {
        if (path == null) return null;
        try {
            String content = Files.readString(Path.of(path), StandardCharsets.UTF_8);
            return JSONUtil.parseObj(content);
        } catch (Exception e) {
            log.warn("读取 JSON 文件失败: path={}, {}", path, e.toString());
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
            log.warn("统计 jsonl 行数失败: path={}, {}", path, e.toString());
            return 0;
        }
    }

    private String readLogTail(String logPath, int lines) {
        if (logPath == null) return "";
        ShellUtil.ShellResult r = ShellUtil.run("tail -" + lines + " " + logPath + " 2>/dev/null | cut -c1-120", 5_000);
        if (r.timedOut() || r.exitCode() != 0) {
            log.warn("读取日志尾部失败: path={}, exit={}, timedOut={}", logPath, r.exitCode(), r.timedOut());
        }
        return r.output().trim();
    }

    /** 脚本是否正在运行 (单次 ps 检查) */
    private boolean isScriptRunning(String scriptName) {
        if (scriptName == null) return false;
        return processSnapshot().containsKey(scriptName);
    }

    /** 单次 ps 快照, 返回 scriptName -> pid (匹配命令中的脚本名) */
    private Map<String, String> processSnapshot() {
        Map<String, String> result = new HashMap<>();
        try {
            ShellUtil.ShellResult r = ShellUtil.run("ps -Ao pid=,command=", 5_000);
            String out = r.output();
            for (String line : out.split("\n")) {
                if (line.trim().isEmpty()) continue;
                String pid = line.trim().split("\\s+", 2)[0];
                String cmd = line.contains(" ") ? line.trim().split("\\s+", 2)[1] : "";
                // 从命令中提取脚本文件名 (xxx.py / xxx.sh)
                java.util.regex.Matcher m = java.util.regex.Pattern.compile("([\\w.]+)\\.(?:py|sh)").matcher(cmd);
                if (m.find()) {
                    result.putIfAbsent(m.group(0), pid);
                }
            }
        } catch (Exception e) {
            log.warn("ps 快照失败: {}", e.getMessage());
        }
        return result;
    }
}
