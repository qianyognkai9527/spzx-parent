package com.joker.spzx.manager.service.videogen;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.mapper.VideoGenTaskMapper;
import com.joker.spzx.manager.service.FileService;
import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.entity.videogen.VideoGenTask;
import com.joker.spzx.utils.AuthContextUtil;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

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
    private KwProviderService providerService;
    @Autowired
    private FileService fileService;
    @Autowired
    private KwConfigService configService;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    private static final int MAX_QUEUE = 20;
    private static final long POLL_TIMEOUT_MS = 15 * 60 * 1000;
    private ThreadPoolExecutor pool;

    @PostConstruct
    public void init() {
        pool = new ThreadPoolExecutor(2, 2, 60, TimeUnit.SECONDS,
                new LinkedBlockingQueue<>(MAX_QUEUE),
                r -> {
                    Thread t = new Thread(r, "videogen");
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
        if (prompt.length() > 2000) throw new IllegalArgumentException("提示词超2000字");
        if (duration == null || (duration != 5 && duration != 10)) throw new IllegalArgumentException("时长仅支持5/10秒");
        if (!List.of("9:16", "1:1", "16:9").contains(ratio)) throw new IllegalArgumentException("比例不支持");
        var provider = providerService.requireActive(
                configService.getProvider(KwConfigService.KEY_VIDEO), "video");
        VideoGenTask t = new VideoGenTask();
        t.setProductId(productId);
        t.setPrompt(prompt);
        t.setPromptSource(promptSource == null ? 1 : promptSource);
        t.setModel(provider.modelFor("video"));
        t.setDuration(duration);
        t.setRatio(ratio);
        t.setStatus(VideoGenTask.ST_QUEUED);
        t.setCreateBy(AuthContextUtil.getUser().getId());
        taskMapper.insert(t);
        submitToPool(t.getId());
        return t.getId();
    }

    public void retry(Long id) {
        VideoGenTask t = taskMapper.selectById(id);
        if (t == null) throw new IllegalArgumentException("任务不存在");
        if (t.getStatus() != VideoGenTask.ST_FAIL) throw new IllegalArgumentException("仅失败任务可重试");
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
            byte[] frame = firstFrameBytes(t.getProductId());
            String body = arkClient.buildSubmitBody(t.getModel(), t.getPrompt(),
                    "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(frame),
                    t.getDuration(), t.getRatio());
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
