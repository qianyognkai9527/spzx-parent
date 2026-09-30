package com.joker.spzx.manager.service.ingest;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.joker.spzx.manager.mapper.IngestBatchMapper;
import com.joker.spzx.manager.mapper.IngestDatasetMapper;
import com.joker.spzx.manager.mapper.SyncAlertMapper;
import com.joker.spzx.manager.service.platform.PlatformRegistryService;
import com.joker.spzx.model.entity.ingest.IngestBatch;
import com.joker.spzx.model.entity.ingest.IngestDataset;
import com.joker.spzx.model.entity.inventory.SyncAlert;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * 采集新鲜度监控（设计 D8：调度留在 cron，后端只判定与告警）。
 *
 * 判据来自 ingest_dataset，两种量法：
 * - table：读事实表的时间列——只有「每次成功运行都无条件写入、且 Java 不写这张表」的数据集能用，
 *   否则后台改一行数据就会把心跳顶成"刚采过"，或者事件表天然的空窗会被误报成挂了。
 * - batch：读 ingest_batch 最近一次成功/部分成功的 finished_at，是 P1 起 Python 的唯一写入路径。
 *
 * 告警落 sync_alert，复用 SyncAlertNotifyTask 已打通的钉钉通道；一轮过期只告一次，
 * 恢复后清 stale_since，下次再过期重新计时。
 */
@Slf4j
@Service
public class IngestFreshnessService {

    /** sync_alert.alert_type，varchar(20) 内 */
    public static final String ALERT_TYPE = "ingest_stale";

    private static final Pattern IDENTIFIER = Pattern.compile("[a-z][a-z0-9_]{0,63}");
    private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final int MESSAGE_MAX = 500;

    @Autowired
    private IngestDatasetMapper datasetMapper;

    @Autowired
    private IngestBatchMapper batchMapper;

    @Autowired
    private SyncAlertMapper syncAlertMapper;

    @Autowired
    private PlatformRegistryService platformRegistryService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /**
     * 数据集健康视图。
     *
     * @param measurable false=配置指向的表/列不存在，无法判定（不告警，前端标"未知"）
     * @param hasBatch   measure=batch 时台账是否有过批次；false=台账刚建立，"查不到批次"是空白而非故障，不判过期
     */
    public record Health(
            String code, String name, Integer platformCode, String measure, Integer slaHours,
            Integer monitor, LocalDateTime lastWriteAt, Long ageHours,
            boolean stale, LocalDateTime staleSince, String writer, boolean measurable,
            boolean hasBatch,
            /* 最近一次跑批台账：看板此前只能读 /tmp 日志，机器一重启就什么都没有 */
            String lastBatchStatus, LocalDateTime lastBatchStartedAt, LocalDateTime lastBatchFinishedAt,
            Integer lastBatchRows, String lastBatchError) {
    }

    /** ingest_batch 里每个数据集最近一条台账（MAX(id)=最后插入的那次运行） */
    private record BatchRow(String status, LocalDateTime startedAt, LocalDateTime finishedAt,
                            Integer rowsTotal, String error) {
    }

    private Map<String, BatchRow> latestBatches() {
        Map<String, BatchRow> byCode = new HashMap<>();
        List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                "SELECT b.dataset, b.status, b.started_at, b.finished_at, b.rows_total, b.error "
                        + "FROM ingest_batch b JOIN (SELECT dataset, MAX(id) max_id FROM ingest_batch "
                        + "GROUP BY dataset) t ON t.max_id = b.id");
        for (Map<String, Object> r : rows) {
            byCode.put(String.valueOf(r.get("dataset")), new BatchRow(
                    str(r.get("status")), ts(r.get("started_at")), ts(r.get("finished_at")),
                    r.get("rows_total") == null ? 0 : ((Number) r.get("rows_total")).intValue(),
                    str(r.get("error"))));
        }
        return byCode;
    }

    private static String str(Object v) {
        return v == null ? null : String.valueOf(v);
    }

    private static LocalDateTime ts(Object v) {
        if (v instanceof Timestamp t) return t.toLocalDateTime();
        if (v instanceof LocalDateTime l) return l;
        return null;
    }

    /** 全部数据集的健康快照，只读，给任务进度页 */
    public List<Health> snapshot() {
        LocalDateTime now = LocalDateTime.now();
        List<IngestDataset> rows = datasetMapper.selectList(
                Wrappers.<IngestDataset>lambdaQuery().orderByDesc(IngestDataset::getMonitor)
                        .orderByAsc(IngestDataset::getCode));
        Map<String, BatchRow> batches = latestBatches();
        List<Health> out = new ArrayList<>(rows.size());
        for (IngestDataset d : rows) {
            LastWrite lw = resolveLastWrite(d);
            Long age = lw.at() == null ? null : java.time.temporal.ChronoUnit.HOURS.between(lw.at(), now);
            BatchRow b = batches.get(d.getCode());
            boolean hasBatch = !IngestDataset.MEASURE_BATCH.equals(d.getMeasure()) || b != null;
            out.add(new Health(d.getCode(), d.getName(), d.getPlatformCode(), d.getMeasure(),
                    d.getSlaHours(), d.getMonitor(), lw.at(), age,
                    isStale(lw.at(), slaOf(d), now) && hasBatch,
                    d.getStaleSince(), d.getWriter(), lw.measurable(), hasBatch,
                    b == null ? null : b.status(), b == null ? null : b.startedAt(),
                    b == null ? null : b.finishedAt(), b == null ? null : b.rowsTotal(),
                    b == null ? null : b.error()));
        }
        return out;
    }

    /** 定时入口：判定 → 状态流转 → 写告警。返回本轮新增告警条数 */
    public int scanStaleness() {
        LocalDateTime now = LocalDateTime.now();
        List<IngestDataset> rows = datasetMapper.selectList(
                Wrappers.<IngestDataset>lambdaQuery().eq(IngestDataset::getMonitor, 1));
        int alerts = 0;
        for (IngestDataset d : rows) {
            try {
                if (checkOne(d, now)) alerts++;
            } catch (Exception e) {
                // 单个数据集判定失败不影响其余；不写状态，下轮重试
                log.warn("ingest 新鲜度判定失败 dataset={}: {}", d.getCode(), e.getMessage());
            }
        }
        return alerts;
    }

    private boolean checkOne(IngestDataset d, LocalDateTime now) {
        // 台账一条批次都没有时，"查不到成功批次"是台账空白而不是采集故障：
        // 契约刚建立就告警等于自摆一条假警，等首轮跑批落了批次再判
        if (IngestDataset.MEASURE_BATCH.equals(d.getMeasure()) && !hasAnyBatch(d.getCode())) {
            log.info("ingest 数据集 {} 跑批台账尚未建立，本轮不判过期", d.getCode());
            return false;
        }
        LastWrite lw = resolveLastWrite(d);
        if (!lw.measurable()) {
            log.warn("ingest_dataset {} 的 measure={} 指向不存在的表/列（{}.{}），跳过判定",
                    d.getCode(), d.getMeasure(), d.getTargetTable(), d.getFreshnessCol());
            return false;
        }
        if (!isStale(lw.at(), slaOf(d), now)) {
            if (d.getStaleSince() != null) {
                datasetMapper.update(null, Wrappers.<IngestDataset>lambdaUpdate()
                        .set(IngestDataset::getStaleSince, null)
                        .eq(IngestDataset::getId, d.getId()));
                log.info("ingest 数据集 {} 恢复新鲜（最后写入 {}）", d.getCode(), lw.at());
            }
            return false;
        }

        if (d.getStaleSince() == null) {
            datasetMapper.update(null, Wrappers.<IngestDataset>lambdaUpdate()
                    .set(IngestDataset::getStaleSince, now)
                    .eq(IngestDataset::getId, d.getId()));
            d.setStaleSince(now);
        }
        if (!shouldAlert(d.getStaleSince(), d.getAlertedAt())) return false;

        long age = lw.at() == null ? -1 : java.time.temporal.ChronoUnit.HOURS.between(lw.at(), now);
        insertAlert(d, lw.at(), age);
        datasetMapper.update(null, Wrappers.<IngestDataset>lambdaUpdate()
                .set(IngestDataset::getAlertedAt, now)
                .eq(IngestDataset::getId, d.getId()));
        return true;
    }

    private void insertAlert(IngestDataset d, LocalDateTime lastWriteAt, long ageHours) {
        SyncAlert alert = new SyncAlert();
        alert.setAlertType(ALERT_TYPE);
        alert.setMessage(truncate(alertMessage(d, lastWriteAt, ageHours), MESSAGE_MAX));
        alert.setOldValue(lastWriteAt == null ? "无" : lastWriteAt.format(TS));
        alert.setNewValue("SLA " + slaOf(d) + "h");
        alert.setStatus(SyncAlert.STATUS_UNREAD);
        alert.setNotified(0);
        alert.setShopId(d.getPlatformCode() == null
                ? null : platformRegistryService.defaultShopId(d.getPlatformCode()));
        alert.setCreateTime(LocalDateTime.now());
        syncAlertMapper.insert(alert);
        log.warn("ingest 过期告警 {}：{}", d.getCode(), alert.getMessage());
    }

    /** 最后写入时刻 + 是否可判定 */
    private record LastWrite(LocalDateTime at, boolean measurable) {
        static LastWrite unknown() { return new LastWrite(null, false); }
    }

    private LastWrite resolveLastWrite(IngestDataset d) {
        if (IngestDataset.MEASURE_BATCH.equals(d.getMeasure())) {
            return new LastWrite(lastBatchAt(d.getCode()), true);
        }
        if (!IngestDataset.MEASURE_TABLE.equals(d.getMeasure())) {
            log.warn("ingest_dataset {} 的 measure 未知: {}", d.getCode(), d.getMeasure());
            return LastWrite.unknown();
        }
        if (!isSafeIdentifier(d.getTargetTable()) || !isSafeIdentifier(d.getFreshnessCol())) {
            return LastWrite.unknown();
        }
        // 标识符只能来自 ingest_dataset 配置，这里用 information_schema 做白名单收口：
        // 必须是当前库真实存在的表 + 该表确有的时间列，配置写错或被人改成别的东西都读不出数据
        Integer ok = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                        + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ? "
                        + "AND DATA_TYPE IN ('datetime', 'timestamp', 'date')",
                Integer.class, d.getTargetTable(), d.getFreshnessCol());
        if (ok == null || ok == 0) return LastWrite.unknown();

        Timestamp ts = jdbcTemplate.queryForObject(
                "SELECT MAX(CAST(`" + d.getFreshnessCol() + "` AS DATETIME)) FROM `" + d.getTargetTable() + "`",
                Timestamp.class);
        return new LastWrite(ts == null ? null : ts.toLocalDateTime(), true);
    }

    /** 台账是否出现过任何批次（含 failed）——决定 batch 数据集能不能判过期 */
    private boolean hasAnyBatch(String datasetCode) {
        Long n = batchMapper.selectCount(
                Wrappers.<IngestBatch>lambdaQuery().eq(IngestBatch::getDataset, datasetCode));
        return n != null && n > 0;
    }

    /** 最近一次「数据确实落库」的批次完成时间：partial 也算，只是有脏行不是没采到 */
    private LocalDateTime lastBatchAt(String datasetCode) {
        List<IngestBatch> rows = batchMapper.selectList(
                Wrappers.<IngestBatch>lambdaQuery()
                        .select(IngestBatch::getFinishedAt)
                        .eq(IngestBatch::getDataset, datasetCode)
                        .in(IngestBatch::getStatus, IngestBatch.LANDED)
                        .isNotNull(IngestBatch::getFinishedAt)
                        .orderByDesc(IngestBatch::getFinishedAt)
                        .last("LIMIT 1"));
        return rows.isEmpty() ? null : rows.get(0).getFinishedAt();
    }

    public static int slaOf(IngestDataset d) {
        return d.getSlaHours() == null || d.getSlaHours() <= 0 ? 48 : d.getSlaHours();
    }

    /** 纯函数：从没写过 = 过期；超过 SLA = 过期。用 Duration 比较，避免整除截断把 30h01m 当成 30h 放过 */
    public static boolean isStale(LocalDateTime lastWriteAt, int slaHours, LocalDateTime now) {
        if (lastWriteAt == null) return true;
        return java.time.Duration.between(lastWriteAt, now)
                .compareTo(java.time.Duration.ofHours(slaHours)) > 0;
    }

    /** 纯函数：一轮过期只告一次——alerted_at 落在本轮起点之后（含同轮）就抑制 */
    public static boolean shouldAlert(LocalDateTime staleSince, LocalDateTime alertedAt) {
        if (staleSince == null) return false;
        return alertedAt == null || alertedAt.isBefore(staleSince);
    }

    /** 纯函数：动态拼进 SQL 的表名/列名只允许小写下划线标识符 */
    public static boolean isSafeIdentifier(String s) {
        return s != null && IDENTIFIER.matcher(s).matches();
    }

    /** 纯函数：告警文案，含排障需要的三件事——多久没写、最后一次是什么时候、该谁动 */
    public static String alertMessage(IngestDataset d, LocalDateTime lastWriteAt, long ageHours) {
        StringBuilder sb = new StringBuilder("「").append(d.getName()).append("」采集已过期：");
        sb.append(ageHours < 0 ? "从未成功写入" : "已 " + ageHours + " 小时没有成功采集")
                .append("（SLA ").append(slaOf(d)).append(" 小时）");
        if (lastWriteAt != null) sb.append("，最后写入 ").append(lastWriteAt.format(TS));
        if (d.getWriter() != null && !d.getWriter().isBlank()) {
            sb.append("，写入方 ").append(d.getWriter());
            if (d.getCronExpr() != null && !d.getCronExpr().isBlank()) {
                sb.append("（cron ").append(d.getCronExpr()).append('）');
            }
        }
        sb.append("。检查对应 Chrome 窗口是否在线/脚本是否报错");
        return sb.toString();
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max);
    }
}
