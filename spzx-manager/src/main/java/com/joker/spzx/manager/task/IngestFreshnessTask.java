package com.joker.spzx.manager.task;

import com.joker.spzx.manager.service.ingest.IngestFreshnessService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 采集数据新鲜度扫描：按 ingest_dataset 的 SLA 判定，过期写 sync_alert（由 SyncAlertNotifyTask 推钉钉）。
 * 采集调度本身留在系统 cron（设计 D8），这里只看「该写的有没有写进来」。
 */
@Slf4j
@Component
@Lazy(false) // dev 开了 lazy-init，定时任务 bean 必须启动即建，否则永不调度
public class IngestFreshnessTask {

    @Autowired
    private IngestFreshnessService ingestFreshnessService;

    /** 默认一小时一次：cron 侧最短的采集是每日，判得更勤也不会更早发现问题，只会空转 */
    @Scheduled(fixedDelayString = "${spzx.ingest.scan-interval-ms:3600000}",
            initialDelayString = "${spzx.ingest.scan-initial-delay-ms:90000}")
    public void scan() {
        try {
            int alerts = ingestFreshnessService.scanStaleness();
            if (alerts > 0) log.info("采集新鲜度：本轮新增 {} 条过期告警", alerts);
        } catch (Exception e) {
            log.warn("采集新鲜度扫描失败: {}", e.getMessage());
        }
    }
}
