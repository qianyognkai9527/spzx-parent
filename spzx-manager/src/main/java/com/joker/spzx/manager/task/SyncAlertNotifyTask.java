package com.joker.spzx.manager.task;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONObject;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.mapper.SyncAlertMapper;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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
@Lazy(false) // dev 开了 lazy-init，定时任务 bean 必须启动即建，否则永不调度
public class SyncAlertNotifyTask {

    @Autowired
    private SyncAlertMapper syncAlertMapper;

    @Value("${spzx.alert.dingtalk-webhook:}")
    private String webhook;

    private static final int BATCH = 20;

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
