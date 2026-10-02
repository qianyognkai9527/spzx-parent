package com.joker.spzx.manager.task;

import com.joker.spzx.manager.service.kw.KwTaskService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Lazy;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * AI 选词定时跑批：把「还没跑过选词」的商品自动建任务，省去每天手动点。
 * 默认关闭（kw.auto-run.enabled=false），在 application-local.yml 打开并配 cron。
 */
@Slf4j
@Component
@Lazy(false) // dev 开了 lazy-init，定时任务必须启动即建，否则永不调度
public class KwAutoRunTask {

    @Autowired
    private KwTaskService kwTaskService;
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Value("${kw.auto-run.enabled:false}")
    private boolean enabled;

    @Value("${kw.auto-run.limit:10}")
    private int limit;

    @Scheduled(cron = "${kw.auto-run.cron:0 30 4 * * ?}")
    public void runPending() {
        if (!enabled) return;
        int n = Math.min(Math.max(limit, 1), 50);
        List<Long> productIds = jdbcTemplate.queryForList(
                "SELECT p.id FROM platform_product p "
                        + "WHERE NOT EXISTS (SELECT 1 FROM kw_select_task t WHERE t.product_id = p.id) "
                        + "AND EXISTS (SELECT 1 FROM product_media m WHERE m.product_id = p.id AND m.file_type = 1) "
                        + "ORDER BY p.id DESC LIMIT ?", Long.class, n);
        if (productIds.isEmpty()) {
            log.debug("kw跑批：无待处理商品");
            return;
        }
        int created = 0;
        for (Long pid : productIds) {
            try {
                kwTaskService.create(pid, null, "定时跑批");
                created++;
            } catch (Exception e) {
                log.warn("kw跑批建任务失败 productId={}: {}", pid, e.getMessage());
            }
        }
        log.info("kw跑批完成：建任务 {} 个（候选 {}）", created, productIds.size());
    }
}
