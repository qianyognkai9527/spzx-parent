package com.joker.spzx.manager.task;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.mapper.SyncAlertMapper;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Lazy;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * sync_alert → 钉钉 webhook 推送。
 * 告警行由 automation/ 下的 Python 脚本直接写库（钩不住插入时机），也由 IngestFreshnessService 写采集过期告警，
 * 统一按分钟扫描 notified=0 的行。
 * webhook 未配置（application-local.yml 的 spzx.alert.dingtalk-webhook 为空）时整个任务空转。
 */
@Slf4j
@Component
@Lazy(false) // 显式保险：实测 Boot 3.3.5 已把 @Scheduled 的 bean 排除在懒初始化之外（不加也会被调度），
    // 留着是为了不依赖这个实现细节
public class SyncAlertNotifyTask {

    @Autowired
    private SyncAlertMapper syncAlertMapper;

    @Value("${spzx.alert.dingtalk-webhook:}")
    private String webhook;

    private static final int BATCH = 20;

    /**
     * 没配 webhook 时这个任务是空转的 —— 空转本身不是问题（告警在后台顶栏与任务进度页可见），
     * 但"为什么我没收到推送"得能从启动日志回答，所以只在启动时说一次。
     */
    @PostConstruct
    void announceChannel() {
        if (webhook == null || webhook.isBlank()) {
            log.info("外部推送通道未配置（spzx.alert.dingtalk-webhook 为空）："
                    + "告警只写进 sync_alert，由后台顶栏「待处理提醒」与任务进度页承载");
        } else {
            log.info("外部推送通道已配置，未读告警每分钟批量推一次（单批最多 {} 条）", BATCH);
        }
    }

    @Scheduled(fixedDelay = 60_000, initialDelay = 30_000)
    public void pushPending() {
        if (webhook == null || webhook.isBlank()) return;
        List<SyncAlert> rows = syncAlertMapper.selectList(new LambdaQueryWrapper<SyncAlert>()
                .eq(SyncAlert::getNotified, 0)
                .orderByAsc(SyncAlert::getId)
                .last("LIMIT " + BATCH));
        if (rows.isEmpty()) return;
        try {
            send(markdownOf(rows));

            // 仅推送成功才标记：失败下轮重试
            syncAlertMapper.update(null, new LambdaUpdateWrapper<SyncAlert>()
                    .set(SyncAlert::getNotified, 1)
                    .in(SyncAlert::getId, rows.stream().map(SyncAlert::getId).toList()));
            log.info("告警已推送 {} 条", rows.size());
        } catch (Exception e) {
            log.warn("告警推送失败，下轮重试: {}", e.getMessage());
        }
    }

    /** 标题不再自称「库存同步提醒」：sync_alert 现在同时承载库存类与采集新鲜度类告警 */
    static String markdownOf(List<SyncAlert> rows) {
        StringBuilder sb = new StringBuilder("### 运营提醒（" + rows.size() + " 条）\n");
        for (SyncAlert a : rows) {
            sb.append("- ").append(a.getMessage() == null ? a.getAlertType() : a.getMessage());
            if (a.getPlatformProductId() != null) {
                sb.append("（商品 ").append(a.getPlatformProductId()).append('）');
            }
            sb.append('\n');
        }
        return sb.toString();
    }

    private void send(String markdown) {
        JSONObject text = new JSONObject().set("title", "运营提醒").set("text", markdown);
        JSONObject body = new JSONObject().set("msgtype", "markdown").set("markdown", text);
        String resp = HttpRequest.post(webhook).body(body.toString()).timeout(5000).execute().body();
        JSONObject r = cn.hutool.json.JSONUtil.parseObj(resp);
        if (r.getInt("errcode", -1) != 0) {
            throw new IllegalStateException("钉钉返回 errcode=" + r.getStr("errcode") + " " + r.getStr("errmsg"));
        }
    }
}
