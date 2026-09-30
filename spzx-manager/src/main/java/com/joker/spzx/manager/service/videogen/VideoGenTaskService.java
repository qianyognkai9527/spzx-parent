package com.joker.spzx.manager.service.videogen;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.mapper.VideoGenTaskMapper;
import com.joker.spzx.manager.service.FileService;
import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.manager.util.VideoPricing;
import com.joker.spzx.model.entity.videogen.VideoGenTask;
import com.joker.spzx.utils.AuthContextUtil;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 视频生成任务服务：创建入队 → 线程池执行器（提交 Ark + 轮询 + 成片转存 MinIO）→ 重试/分页。
 *
 * <p>执行器内无长事务，全部单语句 LambdaUpdateWrapper 更新；
 * 队列满直接落 FAIL + 抛错（不留排队孤儿，吸取 kw 教训）。
 */
@Slf4j
@Service
public class VideoGenTaskService {

    @Autowired
    private VideoGenTaskMapper taskMapper;
    @Autowired
    private ArkVideoClient arkClient;
    @Autowired
    private VideoPromptService promptService;
    @Autowired
    private KwProviderService providerService;
    @Autowired
    private FileService fileService;
    @Autowired
    private KwConfigService configService;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Value("${minio.endpoint:http://127.0.0.1:9000}")
    private String minioEndpoint;
    @Value("${minio.bucket:spzx-manager}")
    private String minioBucket;

    private static final int MAX_QUEUE = 20;
    /** prompt 列宽 VARCHAR(2000)，超长写入会整条 insert/update 报错 */
    private static final int PROMPT_MAX_LEN = 2000;
    private static final long POLL_TIMEOUT_MS = 15 * 60 * 1000;
    private final AtomicInteger threadCounter = new AtomicInteger();
    private ThreadPoolExecutor pool;
    /**
     * 预算校验与入库之间的互斥锁。guardBudget 是「读当日已用 → 判断 → 插一行」三步，
     * 并发下两个请求能同时通过校验，实际扣费翻倍。单实例部署用进程内锁即可，
     * 多实例需要换成 DB 层的计数器行。
     */
    private final Object budgetLock = new Object();

    @PostConstruct
    public void init() {
        pool = new ThreadPoolExecutor(2, 2, 60, TimeUnit.SECONDS,
                new LinkedBlockingQueue<>(MAX_QUEUE),
                r -> {
                    Thread t = new Thread(r, "videogen-" + threadCounter.incrementAndGet());
                    t.setDaemon(true);
                    return t;
                });
    }

    @PreDestroy
    public void destroy() {
        if (pool != null) pool.shutdownNow();
    }

    public Long create(Long productId, String prompt, Integer promptSource, Integer duration, String ratio) {
        // platform_product 无 is_deleted 列（Task4 实测），显式存在性检查避免透传底层 SQL 错误
        if (productId == null) throw new IllegalArgumentException("请先选择商品");
        Integer exists = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM platform_product WHERE id=?", Integer.class, productId);
        if (exists == null || exists == 0) {
            throw new IllegalArgumentException("商品不存在: " + productId);
        }
        if (prompt == null || prompt.isBlank()) throw new IllegalArgumentException("提示词不能为空");
        if (prompt.length() > PROMPT_MAX_LEN) throw new IllegalArgumentException("提示词超" + PROMPT_MAX_LEN + "字");
        if (duration == null || (duration != 5 && duration != 10)) throw new IllegalArgumentException("时长仅支持5/10秒");
        if (!List.of("9:16", "1:1", "16:9").contains(ratio)) throw new IllegalArgumentException("比例不支持");
        var provider = providerService.requireActive(
                configService.getProvider(KwConfigService.KEY_VIDEO), "video");
        BigDecimal est = VideoPricing.estimate(provider.videoPrice(), duration);
        VideoGenTask t = new VideoGenTask();
        t.setProductId(productId);
        t.setPrompt(prompt);
        t.setPromptSource(promptSource == null ? 1 : promptSource);
        t.setModel(provider.modelFor("video"));
        t.setDuration(duration);
        t.setRatio(ratio);
        t.setEstCost(est);
        t.setStatus(VideoGenTask.ST_QUEUED);
        t.setCreateBy(AuthContextUtil.getUser().getId());
        synchronized (budgetLock) {
            guardBudget(est);
            taskMapper.insert(t);
        }
        submitToPool(t.getId());
        return t.getId();
    }

    /** 日预算护栏：当日已产生（含在途）预计扣费 + 本单 > 预算 → 拒绝；预算未配置/非法 = 不拦截 */
    private void guardBudget(BigDecimal est) {
        BigDecimal budget = VideoPricing.parse(configService.getValue(KwConfigService.KEY_VIDEO_BUDGET));
        if (budget == null || budget.signum() <= 0) return;
        BigDecimal spent = todaySpended();
        if (spent.add(est).compareTo(budget) > 0) {
            throw new IllegalArgumentException(String.format(
                    "超出视频日预算：已用 ¥%s + 本单预计 ¥%s > 预算 ¥%s（可在 AI引擎配置 页调整）",
                    spent.toPlainString(), est.toPlainString(), budget.toPlainString()));
        }
    }

    /** 当日创建任务（含排队/在途，软删除外）的预计扣费合计 */
    private BigDecimal todaySpended() {
        BigDecimal sum = jdbcTemplate.queryForObject(
                "SELECT COALESCE(SUM(est_cost),0) FROM video_gen_task "
                        + "WHERE is_deleted=0 AND create_time >= CURDATE() AND create_time < CURDATE() + INTERVAL 1 DAY",
                BigDecimal.class);
        return sum == null ? BigDecimal.ZERO : sum;
    }

    /** 给前端的计费预览：模型/5秒档单价/本单预计/日预算/当日已用 */
    public Map<String, Object> costEstimate(Integer duration) {
        var provider = providerService.requireActive(
                configService.getProvider(KwConfigService.KEY_VIDEO), "video");
        int d = (duration == null || duration <= 0) ? 5 : duration;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("model", provider.modelFor("video"));
        out.put("videoPrice", provider.videoPrice());
        out.put("estCost", VideoPricing.estimate(provider.videoPrice(), d));
        out.put("dailyBudget", VideoPricing.parse(configService.getValue(KwConfigService.KEY_VIDEO_BUDGET)));
        out.put("todaySpend", todaySpended());
        return out;
    }

    /**
     * 批量建任务：提示词留空，由工作线程逐个调视觉模型生成后提交 Ark（HTTP 请求不阻塞在 N 次 vision 上）。
     * 预算按整批合计一次校验；不存在的商品进 skipped，不入队。
     */
    public Map<String, Object> createBatch(List<Long> productIds, Integer duration, String ratio) {
        if (productIds == null || productIds.isEmpty()) throw new IllegalArgumentException("请先选择商品");
        List<Long> ids = productIds.stream().filter(java.util.Objects::nonNull).distinct().toList();
        if (ids.isEmpty()) throw new IllegalArgumentException("请先选择商品");
        if (ids.size() > MAX_QUEUE) throw new IllegalArgumentException("单批最多 " + MAX_QUEUE + " 个商品");
        if (duration == null || (duration != 5 && duration != 10)) throw new IllegalArgumentException("时长仅支持5/10秒");
        if (!List.of("9:16", "1:1", "16:9").contains(ratio)) throw new IllegalArgumentException("比例不支持");
        var provider = providerService.requireActive(
                configService.getProvider(KwConfigService.KEY_VIDEO), "video");
        String placeholders = String.join(",", ids.stream().map(x -> "?").toList());
        List<Long> found = jdbcTemplate.queryForList(
                "SELECT id FROM platform_product WHERE id IN (" + placeholders + ")", Long.class,
                ids.toArray());
        BigDecimal est = VideoPricing.estimate(provider.videoPrice(), duration);
        List<Long> created = new ArrayList<>();
        List<Long> skipped = new ArrayList<>(ids);
        skipped.removeAll(found);
        Long uid = AuthContextUtil.getUser().getId();
        synchronized (budgetLock) {
            guardBudget(est.multiply(BigDecimal.valueOf(found.size())));
            for (Long pid : found) {
                VideoGenTask t = new VideoGenTask();
                t.setProductId(pid);
                t.setPrompt("");
                t.setPromptSource(1);
                t.setModel(provider.modelFor("video"));
                t.setDuration(duration);
                t.setRatio(ratio);
                t.setEstCost(est);
                t.setStatus(VideoGenTask.ST_QUEUED);
                t.setCreateBy(uid);
                taskMapper.insert(t);
                created.add(t.getId());
            }
        }
        List<Long> rejected = new ArrayList<>();
        for (Long taskId : created) {
            try {
                pool.execute(() -> run(taskId));
            } catch (RejectedExecutionException e) {
                taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                        .set(VideoGenTask::getStatus, VideoGenTask.ST_FAIL)
                        .set(VideoGenTask::getErrorMsg, "任务队列已满，请稍后重试").eq(VideoGenTask::getId, taskId));
                rejected.add(taskId);
            }
        }
        // 没受理成功的不能算进 created/estCostTotal，否则前端报「已创建 N 个 / 预计扣 ¥X」是虚的
        created.removeAll(rejected);
        skipped.addAll(rejected);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("created", created);
        out.put("skipped", skipped);
        out.put("estCostTotal", est.multiply(BigDecimal.valueOf(created.size())));
        return out;
    }

    public void retry(Long id) {
        VideoGenTask t = taskMapper.selectById(id);
        if (t == null) throw new IllegalArgumentException("任务不存在");
        if (t.getStatus() != VideoGenTask.ST_FAIL) throw new IllegalArgumentException("仅失败任务可重试");
        // 重试同样按本单预计扣费过日预算护栏（Ark 侧重复计费风险）
        guardBudget(t.getEstCost() == null ? VideoPricing.ZERO : t.getEstCost());
        // 原子抢占 FAIL→QUEUED：并发重试仅一方 update 命中，防止双提交 Ark
        int claimed = taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                .set(VideoGenTask::getStatus, VideoGenTask.ST_QUEUED)
                .set(VideoGenTask::getErrorMsg, null).set(VideoGenTask::getRemoteTaskId, null)
                .set(VideoGenTask::getFinishTime, null)
                .eq(VideoGenTask::getId, id)
                .eq(VideoGenTask::getStatus, VideoGenTask.ST_FAIL));
        if (claimed == 0) throw new IllegalArgumentException("任务状态已变更，请刷新");
        submitToPool(id);
    }

    public VideoGenTask getById(Long id) {
        return taskMapper.selectById(id);
    }

    /** 软删（TableLogic），MinIO 对象保留，后续做清理任务 */
    public void delete(Long id) {
        taskMapper.deleteById(id);
    }

    private void submitToPool(Long id) {
        try {
            pool.execute(() -> run(id));
        } catch (RejectedExecutionException e) {
            taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                    .set(VideoGenTask::getStatus, VideoGenTask.ST_FAIL)
                    .set(VideoGenTask::getErrorMsg, "任务队列已满，请稍后重试").eq(VideoGenTask::getId, id));
            throw new IllegalArgumentException("任务队列已满，请稍后重试");
        }
    }

    private void run(Long id) {
        VideoGenTask t = taskMapper.selectById(id);
        if (t == null || t.getStatus() != VideoGenTask.ST_QUEUED) return;
        try {
            var provider = providerService.requireActive(
                    configService.getProvider(KwConfigService.KEY_VIDEO), "video");
            String prompt = t.getPrompt();
            if (prompt == null || prompt.isBlank()) { // 批量任务：入队时不带提示词，此处现场生成并回写
                prompt = promptService.generate(t.getProductId()).prompt();
                if (prompt == null || prompt.isBlank()) throw new RuntimeException("提示词生成结果为空");
                // 模型产出长度不可控，超列宽直接写库失败，截断比整单失败更划算
                if (prompt.length() > PROMPT_MAX_LEN) prompt = prompt.substring(0, PROMPT_MAX_LEN);
                taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                        .set(VideoGenTask::getPrompt, prompt).eq(VideoGenTask::getId, id));
            }
            byte[] frame = firstFrameBytes(t.getProductId());
            String body = arkClient.buildSubmitBody(t.getModel(), prompt,
                    "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(frame),
                    t.getDuration());
            String remoteId = arkClient.submit(provider, body);
            taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                    .set(VideoGenTask::getStatus, VideoGenTask.ST_SUBMITTED)
                    .set(VideoGenTask::getRemoteTaskId, remoteId).eq(VideoGenTask::getId, id));
            long deadline = System.currentTimeMillis() + POLL_TIMEOUT_MS;
            int consecutiveErr = 0;
            int lastStatus = VideoGenTask.ST_SUBMITTED; // 提交时已写入，轮询中状态未变则跳过重复写
            while (System.currentTimeMillis() < deadline) {
                Thread.sleep(consecutiveErr > 0 ? 15_000 : 5_000);
                ArkVideoClient.ArkStatus st;
                try {
                    st = arkClient.poll(provider, remoteId);
                    consecutiveErr = 0;
                } catch (Exception e) {
                    if (++consecutiveErr >= 3) throw new RuntimeException("Ark查询连续失败: " + e.getMessage());
                    continue;
                }
                switch (st.state()) {
                    case "succeeded" -> {
                        if (st.videoUrl() == null) throw new RuntimeException("成功但无video_url");
                        byte[] mp4 = fileService.readBytes(st.videoUrl());
                        String key = "videogen/" + cn.hutool.core.date.DateUtil.format(new Date(), "yyyyMMdd")
                                + "/" + UUID.randomUUID().toString().replace("-", "") + ".mp4";
                        fileService.uploadBytes(key, mp4, "video/mp4");
                        taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                                .set(VideoGenTask::getStatus, VideoGenTask.ST_DONE)
                                .set(VideoGenTask::getObjectKey, key)
                                .set(VideoGenTask::getFinishTime, LocalDateTime.now())
                                .eq(VideoGenTask::getId, id));
                        log.info("videogen任务成功 id={} size={}B", id, mp4.length);
                        return;
                    }
                    case "failed" -> throw new RuntimeException(st.errorMsg() == null ? "生成失败" : st.errorMsg());
                    default -> { // queued/running → 状态推进（仅在状态实际变化时写库）
                        int next = "running".equals(st.state())
                                ? VideoGenTask.ST_RUNNING : VideoGenTask.ST_SUBMITTED;
                        if (next != lastStatus) {
                            taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                                    .set(VideoGenTask::getStatus, next)
                                    .eq(VideoGenTask::getId, id));
                            lastStatus = next;
                        }
                    }
                }
            }
            throw new RuntimeException("生成超时(15min)，已放弃轮询");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            markFail(id, "被中断");
        } catch (Exception e) {
            log.error("videogen任务失败 id={}", id, e);
            String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
            markFail(id, msg.length() > 490 ? msg.substring(0, 490) : msg);
        }
    }

    /**
     * 成片挂回商品媒体（product_media file_type=2）。
     * remark 固定带「AI生成」标识（《人工智能生成合成内容标识办法》要求）。
     * 同一 file_url 已存在则视为已挂载，返回原行 id。
     */
    @Transactional
    public Long attachToProductMedia(Long id) {
        VideoGenTask t = taskMapper.selectById(id);
        if (t == null) throw new IllegalArgumentException("任务不存在");
        if (t.getStatus() != VideoGenTask.ST_DONE || t.getObjectKey() == null || t.getObjectKey().isBlank()) {
            throw new IllegalArgumentException("仅生成成功的任务可挂载");
        }
        String url = objectUrl(t.getObjectKey());
        List<Long> exists = jdbcTemplate.queryForList(
                "SELECT id FROM product_media WHERE product_id=? AND file_type=2 AND file_url=? LIMIT 1",
                Long.class, t.getProductId(), url);
        if (!exists.isEmpty()) return exists.get(0);

        List<Map<String, Object>> bases = jdbcTemplate.queryForList(
                "SELECT person_id, platform_type FROM product_media WHERE product_id=? ORDER BY id LIMIT 1",
                t.getProductId());
        if (bases.isEmpty()) throw new IllegalArgumentException("该商品还没有任何媒体记录，无法挂载视频");
        Object personId = bases.get(0).get("person_id");
        Object platformType = bases.get(0).get("platform_type");
        Integer maxPos = jdbcTemplate.queryForObject(
                "SELECT COALESCE(MAX(img_pos),0) FROM product_media WHERE product_id=? AND file_type=2",
                Integer.class, t.getProductId());
        jdbcTemplate.update("INSERT INTO product_media (product_id, file_type, img_pos, file_name, file_url,"
                        + " person_id, state, create_by, create_time, remark, platform_type)"
                        + " VALUES (?,?,?,?,?,?,?,?,NOW(),?,?)",
                t.getProductId(), 2, (maxPos == null ? 0 : maxPos) + 1,
                t.getObjectKey().substring(t.getObjectKey().lastIndexOf('/') + 1), url,
                personId, 1L, AuthContextUtil.getUser().getId(), "AI生成视频(任务#" + id + ")", platformType);
        Long mediaId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
        log.info("videogen成片挂载商品媒体 task_id={} media_id={}", id, mediaId);
        return mediaId;
    }

    /**
     * MinIO 对象的访问 URL。列表页与挂载 product_media 必须用同一个拼接口径：
     * 挂载去重按 file_url 逐字节比较，两处写法一旦分叉就会重复插入媒体行。
     */
    public String objectUrl(String objectKey) {
        return minioEndpoint + "/" + minioBucket + "/" + objectKey;
    }

    private void markFail(Long id, String msg) {
        taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                .set(VideoGenTask::getStatus, VideoGenTask.ST_FAIL).set(VideoGenTask::getErrorMsg, msg)
                .set(VideoGenTask::getFinishTime, LocalDateTime.now()).eq(VideoGenTask::getId, id));
    }

    private byte[] firstFrameBytes(Long productId) {
        List<String> urls = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 ORDER BY img_pos LIMIT 1",
                String.class, productId);
        if (urls.isEmpty()) throw new IllegalArgumentException("商品无主图，无法图生视频");
        return fileService.readBytes(urls.get(0));
    }

    public IPage<VideoGenTask> page(long pageNum, long pageSize, Integer status, Long productId) {
        return taskMapper.selectPage(PageQueryUtil.of(pageNum, pageSize),
                new LambdaQueryWrapper<VideoGenTask>()
                        .eq(status != null, VideoGenTask::getStatus, status)
                        .eq(productId != null, VideoGenTask::getProductId, productId)
                        .orderByDesc(VideoGenTask::getId));
    }
}
