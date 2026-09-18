package com.joker.spzx.manager.service.kw;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.*;
import com.joker.spzx.model.entity.kw.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class KwTaskService {

    public static final int ST_PENDING = 0, ST_PROFILE = 1, ST_SELECT = 2, ST_DONE = 3, ST_FAIL = 4;

    private static final ThreadPoolExecutor POOL = new ThreadPoolExecutor(
            1, 1, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>(100),
            r -> {
                Thread t = new Thread(r, "kw-task");
                t.setDaemon(true);
                return t;
            });

    @Autowired private KwSelectTaskMapper taskMapper;
    @Autowired private KwTaskWordMapper wordMapper;
    @Autowired private KwTitleSuggestionMapper titleMapper;
    @Autowired private KwProductAnalysisMapper analysisMapper;
    @Autowired private KwWordbankItemMapper wordbankItemMapper;
    @Autowired private KwAiClient aiClient;
    @Autowired private KwConfigService configService;
    @Autowired private KwProperties props;
    @Autowired private JdbcTemplate jdbcTemplate;

    public KwSelectTaskMapper getTaskMapper() {
        return taskMapper;
    }

    public Long create(Long productId, Long batchId, String note) {
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT id, code, title, platform_type FROM platform_product WHERE id=?", productId);
        KwSelectTask task = new KwSelectTask();
        task.setProductId(productId);
        task.setBatchId(batchId);
        task.setNote(note);
        task.setStatus(ST_PENDING);
        task.setTextProvider(configService.getProvider(KwConfigService.KEY_TEXT));
        taskMapper.insert(task);
        submit(task.getId());
        return task.getId();
    }

    public void retry(Long taskId) {
        KwSelectTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new RuntimeException("任务不存在");
        }
        if (task.getStatus() != ST_FAIL) {
            throw new RuntimeException("仅失败任务可重试");
        }
        task.setStatus(ST_PENDING);
        task.setErrorMsg(null);
        task.setTextProvider(configService.getProvider(KwConfigService.KEY_TEXT));
        taskMapper.updateById(task);
        submit(taskId);
    }

    private void submit(Long taskId) {
        POOL.execute(() -> run(taskId));
    }

    private void run(Long taskId) {
        try {
            KwSelectTask task = taskMapper.selectById(taskId);
            if (task == null) {
                return;
            }
            Long analysisId = task.getAnalysisId();
            JSONObject profile;
            if (analysisId == null) {
                // ② 识品
                task.setStatus(ST_PROFILE);
                taskMapper.updateById(task);
                profile = doProfile(task);
                KwProductAnalysis an = new KwProductAnalysis();
                an.setProductId(task.getProductId());
                Map<String, Object> product = jdbcTemplate.queryForMap(
                        "SELECT platform_type, title FROM platform_product WHERE id=?", task.getProductId());
                an.setPlatformType((Integer) product.get("platform_type"));
                an.setTitle((String) product.get("title"));
                List<String> imgs = jdbcTemplate.queryForList(
                        "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                                + "ORDER BY img_pos LIMIT " + props.getImageCount(), String.class, task.getProductId());
                an.setImages(JSONUtil.toJsonStr(imgs));
                an.setAiDesc(profile.toString());
                an.setNote(task.getNote());
                analysisMapper.insert(an);
                task.setAnalysisId(an.getId());
                taskMapper.updateById(task);
            } else {
                profile = JSONUtil.parseObj(analysisMapper.selectById(analysisId).getAiDesc());
            }
            // ③ 选词
            task.setStatus(ST_SELECT);
            taskMapper.updateById(task);
            doSelect(task, profile);
            // 标题
            doTitles(task, profile);
            task.setStatus(ST_DONE);
            task.setFinishTime(LocalDateTime.now());
            taskMapper.updateById(task);
            log.info("kw任务完成: id={}", taskId);
        } catch (Exception e) {
            log.error("kw任务失败: id={}", taskId, e);
            KwSelectTask task = taskMapper.selectById(taskId);
            if (task != null) {
                task.setStatus(ST_FAIL);
                String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                task.setErrorMsg(msg.length() > 490 ? msg.substring(0, 490) : msg);
                taskMapper.updateById(task);
            }
        }
    }

    private JSONObject doProfile(KwSelectTask task) {
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT title, platform_type FROM platform_product WHERE id=?", task.getProductId());
        String title = String.valueOf(product.get("title"));
        List<String> imgs = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                        + "ORDER BY img_pos LIMIT " + props.getImageCount(), String.class, task.getProductId());
        StringBuilder sb = new StringBuilder();
        sb.append("你是电商选品专家。根据商品图和标题分析产品，输出严格JSON：\n");
        sb.append("{\"category\":\"叶子类目\",\"material\":\"材质\",\"fit\":\"版型\",");
        sb.append("\"audience\":{\"gender\":\"\",\"age\":\"\",\"scene\":\"\"},\"style\":\"风格\",");
        sb.append("\"season\":\"季节\",\"selling_points\":[\"卖点\"],");
        sb.append("\"exclude_dims\":[{\"dim\":\"维度名\",\"avoid_keywords\":[\"排除词\"]}],");
        sb.append("\"seed_keywords\":[\"品类核心词\"]}\n");
        sb.append("规则：\n");
        sb.append("1. audience 填目标人群（性别/年龄段/使用场景）\n");
        sb.append("2. exclude_dims 列出该产品不应触达的人群/场景维度及对应关键词（如成人商品排除\"儿童,童,学生\"），2-4 条\n");
        sb.append("3. seed_keywords 列 5-10 个品类核心词\n");
        sb.append("4. 只输出 JSON，不要解释\n");
        sb.append("商品标题：").append(title).append("\n");
        if (task.getNote() != null && !task.getNote().isBlank()) {
            sb.append("补充说明：").append(task.getNote()).append("\n");
        }
        List<Map<String, Object>> parts = new ArrayList<>();
        Map<String, Object> textPart = new LinkedHashMap<>();
        textPart.put("type", "text");
        textPart.put("text", sb.toString());
        parts.add(textPart);
        for (String url : imgs) {
            Map<String, Object> imgPart = new LinkedHashMap<>();
            imgPart.put("type", "image_url");
            Map<String, Object> inner = new LinkedHashMap<>();
            inner.put("url", url);
            imgPart.put("image_url", inner);
            parts.add(imgPart);
        }
        String provider = configService.getProvider(KwConfigService.KEY_VISION);
        String content = aiClient.vision(provider, parts);
        int s = content.indexOf('{');
        int e = content.lastIndexOf('}');
        if (s < 0 || e <= s) {
            throw new RuntimeException("识品返回非JSON: " + content.substring(0, Math.min(100, content.length())));
        }
        return JSONUtil.parseObj(content.substring(s, e + 1));
    }

    private void doSelect(KwSelectTask task, JSONObject profile) {
        // 收集排除关键词
        List<String> avoid = new ArrayList<>();
        JSONArray dims = profile.getJSONArray("exclude_dims");
        if (dims != null) {
            for (Object o : dims) {
                JSONArray kws = ((JSONObject) o).getJSONArray("avoid_keywords");
                if (kws != null) {
                    for (Object k : kws) {
                        avoid.add(String.valueOf(k));
                    }
                }
            }
        }
        // 粗筛 + TopN
        List<KwWordbankItem> bank = wordbankItemMapper.selectList(
                new LambdaQueryWrapper<KwWordbankItem>()
                        .eq(KwWordbankItem::getBatchId, task.getBatchId())
                        .orderByDesc(KwWordbankItem::getScore)
                        .last("LIMIT " + props.getTopN()));
        List<KwWordbankItem> filtered = new ArrayList<>();
        for (KwWordbankItem it : bank) {
            boolean bad = false;
            for (String a : avoid) {
                if (!a.isBlank() && it.getKeyword().contains(a)) {
                    bad = true;
                    break;
                }
            }
            if (!bad) {
                filtered.add(it);
            }
        }
        Map<String, BigDecimal> bankScores = new HashMap<>();
        for (KwWordbankItem it : filtered) {
            bankScores.put(it.getKeyword(), it.getScore());
        }
        // 分批
        int batch = props.getBatchSize();
        for (int i = 0; i < filtered.size(); i += batch) {
            List<KwWordbankItem> chunk = filtered.subList(i, Math.min(i + batch, filtered.size()));
            StringBuilder wordLines = new StringBuilder();
            for (KwWordbankItem it : chunk) {
                wordLines.append(it.getKeyword()).append("|")
                        .append(nz(it.getSearchPopularity())).append("|")
                        .append(it.getClickRate() == null ? 0 : it.getClickRate()).append("|")
                        .append(it.getConvRate() == null ? 0 : it.getConvRate()).append("|")
                        .append(nz(it.getBuyerCount())).append("\n");
            }
            String prompt = "你是淘宝付费推广选词专家。产品画像JSON：\n" + profile.toString()
                    + "\n候选词列表（关键词|搜索人气|点击率|转化率|买家数）：\n" + wordLines
                    + "\n任务：为该产品评估每个词的匹配度。match_score 0-100：完全契合人群/品类/卖点给 80 以上，沾边 50-79，不匹配低于 50（仍要输出，不要删词）。\n"
                    + "reason 用一句话说明匹配或不匹配的原因。\n"
                    + "只输出 JSON 数组 [{\"keyword\":\"词\",\"match_score\":85,\"reason\":\"一句话\"}]，不要输出其他内容。";
            String provider = configService.getProvider(KwConfigService.KEY_TEXT);
            String content = aiClient.text(provider, prompt);
            int s = content.indexOf('[');
            int e = content.lastIndexOf(']');
            if (s < 0 || e <= s) {
                throw new RuntimeException("选词返回非JSON(批 " + (i / batch + 1) + ")");
            }
            JSONArray arr = JSONUtil.parseArray(content.substring(s, e + 1));
            for (Object o : arr) {
                JSONObject w = (JSONObject) o;
                String kw = w.getStr("keyword", "").trim();
                if (kw.isEmpty() || !bankScores.containsKey(kw)) {
                    continue;
                }
                KwTaskWord tw = new KwTaskWord();
                tw.setTaskId(task.getId());
                tw.setKeyword(kw);
                tw.setMatchScore(w.getInt("match_score", 0));
                tw.setBankScore(bankScores.get(kw));
                String reason = w.getStr("reason", "");
                tw.setReason(reason.length() > 190 ? reason.substring(0, 190) : reason);
                tw.setPicked(0);
                wordMapper.insert(tw);
            }
        }
    }

    private void doTitles(KwSelectTask task, JSONObject profile) {
        List<KwTaskWord> top = wordMapper.selectList(
                new LambdaQueryWrapper<KwTaskWord>()
                        .eq(KwTaskWord::getTaskId, task.getId())
                        .orderByDesc(KwTaskWord::getMatchScore)
                        .last("LIMIT 30"));
        if (top.isEmpty()) {
            return;
        }
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT title FROM platform_product WHERE id=?", task.getProductId());
        StringBuilder words = new StringBuilder();
        for (KwTaskWord w : top) {
            words.append(w.getKeyword()).append("(").append(w.getMatchScore()).append(") ");
        }
        String prompt = "你是淘宝标题优化专家。原标题：" + product.get("title")
                + "\n产品画像：" + profile
                + "\n高分匹配词（按匹配度排序）：" + words
                + "\n生成 3 个优化标题：\n"
                + "1. 每个不超过 30 个汉字\n"
                + "2. 自然融入高分词，不堆砌、不无意义重复\n"
                + "3. 不含广告法违禁词（最/第一/顶级/极致/100%等一律不用）\n"
                + "4. 空格分隔不同卖点短语\n"
                + "只输出 JSON 数组 [{\"title\":\"...\",\"reason\":\"一句话\"}]。";
        String provider = configService.getProvider(KwConfigService.KEY_TEXT);
        String content = aiClient.text(provider, prompt);
        int s = content.indexOf('[');
        int e = content.lastIndexOf(']');
        if (s < 0 || e <= s) {
            return; // 标题是加分项，失败不致命
        }
        JSONArray arr = JSONUtil.parseArray(content.substring(s, e + 1));
        for (Object o : arr) {
            JSONObject t = (JSONObject) o;
            String title = t.getStr("title", "").trim();
            if (title.isEmpty() || title.length() > 60) {
                continue;
            }
            KwTitleSuggestion ts = new KwTitleSuggestion();
            ts.setTaskId(task.getId());
            ts.setTitle(title);
            ts.setReason(t.getStr("reason", ""));
            titleMapper.insert(ts);
        }
    }

    public Map<String, Object> detail(Long taskId) {
        KwSelectTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new RuntimeException("任务不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("task", task);
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT code, title, pricing FROM platform_product WHERE id=?", task.getProductId());
        out.put("productTitle", product.get("title"));
        out.put("productCode", product.get("code"));
        if (task.getAnalysisId() != null) {
            KwProductAnalysis an = analysisMapper.selectById(task.getAnalysisId());
            out.put("profile", an == null ? null : an.getAiDesc());
        }
        out.put("words", wordMapper.selectList(new LambdaQueryWrapper<KwTaskWord>()
                .eq(KwTaskWord::getTaskId, taskId)
                .orderByDesc(KwTaskWord::getMatchScore)));
        out.put("titles", titleMapper.selectList(new LambdaQueryWrapper<KwTitleSuggestion>()
                .eq(KwTitleSuggestion::getTaskId, taskId)));
        return out;
    }

    public void pickWords(Long taskId, List<Long> wordIds) {
        for (Long id : wordIds) {
            KwTaskWord w = wordMapper.selectById(id);
            if (w != null && w.getTaskId().equals(taskId)) {
                w.setPicked(w.getPicked() != null && w.getPicked() == 1 ? 0 : 1);
                wordMapper.updateById(w);
            }
        }
    }

    public void pickTitles(Long taskId, List<Long> titleIds) {
        for (Long id : titleIds) {
            KwTitleSuggestion t = titleMapper.selectById(id);
            if (t != null && t.getTaskId().equals(taskId)) {
                t.setPicked(t.getPicked() != null && t.getPicked() == 1 ? 0 : 1);
                titleMapper.updateById(t);
            }
        }
    }

    private int nz(Integer v) {
        return v == null ? 0 : v;
    }
}
