package com.joker.spzx.manager.service.ingest;

import com.joker.spzx.model.entity.ingest.IngestDataset;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 纯函数单测：新鲜度判定、一轮只告一次、动态 SQL 标识符白名单、告警文案。
 * 不连库——ingest_dataset 的真实配置由 sql/ingest_contract_p1a_verify.sql 的 V3 自检覆盖。
 */
class IngestFreshnessServiceTest {

    private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 29, 12, 0);

    private static IngestDataset dataset(String measure, String table, String col) {
        IngestDataset d = new IngestDataset();
        d.setCode("item_daily_sycm");
        d.setName("淘宝商品日效果快照");
        d.setMeasure(measure);
        d.setTargetTable(table);
        d.setFreshnessCol(col);
        d.setSlaHours(30);
        d.setWriter("automation/sourcing/sycm_item_snapshot.py");
        d.setCronExpr("0 6 * * *");
        return d;
    }

    @Test
    void 恰好等于SLA不算过期超过才算() {
        assertFalse(IngestFreshnessService.isStale(NOW.minusHours(30), 30, NOW));
        assertTrue(IngestFreshnessService.isStale(NOW.minusHours(30).minusMinutes(1), 30, NOW));
    }

    @Test
    void 从未写入视为过期() {
        assertTrue(IngestFreshnessService.isStale(null, 30, NOW));
    }

    @Test
    void sla缺省或非法回落到48() {
        IngestDataset d = new IngestDataset();
        d.setSlaHours(null);
        assertEquals(48, IngestFreshnessService.slaOf(d));
        d.setSlaHours(0);
        assertEquals(48, IngestFreshnessService.slaOf(d));
        d.setSlaHours(-5);
        assertEquals(48, IngestFreshnessService.slaOf(d));
        d.setSlaHours(192);
        assertEquals(192, IngestFreshnessService.slaOf(d));
    }

    @Test
    void 一轮过期只告一次_恢复后再过期重新告() {
        LocalDateTime episode = NOW.minusHours(2);
        assertTrue(IngestFreshnessService.shouldAlert(episode, null), "本轮首次应告警");
        assertFalse(IngestFreshnessService.shouldAlert(episode, NOW), "已在本轮内告过则抑制");
        assertFalse(IngestFreshnessService.shouldAlert(episode, episode), "告警时间等于起点也视为已告");
        assertTrue(IngestFreshnessService.shouldAlert(NOW, episode), "恢复后重新过期→重新告警");
        assertFalse(IngestFreshnessService.shouldAlert(null, null), "未进入过期态不告警");
    }

    @Test
    void 标识符白名单挡住拼接注入() {
        assertTrue(IngestFreshnessService.isSafeIdentifier("source_sku"));
        assertTrue(IngestFreshnessService.isSafeIdentifier("sycm_item_effect_history"));
        assertFalse(IngestFreshnessService.isSafeIdentifier("sycm_item_effect_history; drop table x"));
        assertFalse(IngestFreshnessService.isSafeIdentifier("`snapshot_time`"));
        assertFalse(IngestFreshnessService.isSafeIdentifier("snapshot_time --"));
        assertFalse(IngestFreshnessService.isSafeIdentifier("UPPER_CASE"));
        assertFalse(IngestFreshnessService.isSafeIdentifier("1abc"));
        assertFalse(IngestFreshnessService.isSafeIdentifier(""));
        assertFalse(IngestFreshnessService.isSafeIdentifier(null));
    }

    @Test
    void 告警文案含时长_SLA_最后写入与写入方() {
        // 与本机实况同形：09-27 06:03 最后一次快照，09-29 12:00 判定
        String msg = IngestFreshnessService.alertMessage(
                dataset("table", "sycm_item_effect_history", "snapshot_time"),
                LocalDateTime.of(2026, 9, 27, 6, 0), 54);
        assertTrue(msg.contains("淘宝商品日效果快照"), msg);
        assertTrue(msg.contains("已 54 小时"), msg);
        assertTrue(msg.contains("SLA 30 小时"), msg);
        assertTrue(msg.contains("最后写入 2026-09-27 06:00"), msg);
        assertTrue(msg.contains("sycm_item_snapshot.py"), msg);
        assertTrue(msg.contains("cron 0 6 * * *"), msg);
    }

    @Test
    void 从未写入的文案不假装有时间() {
        String msg = IngestFreshnessService.alertMessage(
                dataset("batch", null, null), null, -1);
        assertTrue(msg.contains("从未成功写入"), msg);
        assertTrue(!msg.contains("最后写入"), msg);
    }

    @Test
    void 列宽取满时文案仍装得进告警列() {
        IngestDataset d = dataset("table", "sycm_item_effect_history", "snapshot_time");
        d.setName("名".repeat(64));            // name varchar(64)
        d.setWriter("w".repeat(128));          // writer varchar(128)
        d.setCronExpr("0 6 * * * 0 6 * * * 0 6 * * *"); // cron_expr varchar(32)
        String msg = IngestFreshnessService.alertMessage(d, NOW.minusHours(9999), 9999);
        assertTrue(msg.length() <= 500, "message varchar(500) 装不下: " + msg.length());
    }

    @Test
    void skipped提醒后续落库即销案_含partial() {
        // 实况：10-03 06:00 报「生意参谋每日快照未落库」，10-06 06:00 落了 10 行（partial）
        var landed = new IngestFreshnessService.Landed(LocalDateTime.of(2026, 10, 6, 6, 0), null);
        assertTrue(IngestFreshnessService.recoveredBy("cron_skipped",
                LocalDateTime.of(2026, 10, 3, 6, 0), landed), "真写了行，「未落库」就该翻篇");
    }

    @Test
    void failed提醒只认success_否则覆盖率闸门白装() {
        var partialOnly = new IngestFreshnessService.Landed(LocalDateTime.of(2026, 10, 6, 6, 0), null);
        assertFalse(IngestFreshnessService.recoveredBy("cron_failed",
                LocalDateTime.of(2026, 10, 6, 6, 0), partialOnly),
                "下一轮同样 partial 不能把自己吞掉（10-06 那条只落 10 行的告警至今未恢复）");
        var thenSuccess = new IngestFreshnessService.Landed(
                LocalDateTime.of(2026, 10, 7, 6, 0), LocalDateTime.of(2026, 10, 7, 6, 0));
        assertTrue(IngestFreshnessService.recoveredBy("cron_failed",
                LocalDateTime.of(2026, 10, 6, 6, 0), thenSuccess), "来一次干净成功才算恢复");
    }

    @Test
    void 同一轮的台账不能给自己销案() {
        // 同一轮里 cron_batch 先 end、cron_alert 后写，时刻只差几秒
        var same = new IngestFreshnessService.Landed(LocalDateTime.of(2026, 10, 6, 6, 0, 37), null);
        assertFalse(IngestFreshnessService.recoveredBy("cron_skipped",
                LocalDateTime.of(2026, 10, 6, 6, 0, 38), same), "必须严格晚于提醒本身");
        assertFalse(IngestFreshnessService.recoveredBy("cron_skipped",
                LocalDateTime.of(2026, 10, 6, 6, 0, 37), same), "相等也不算");
    }

    @Test
    void 没落过库或提醒没时间就不销案() {
        assertFalse(IngestFreshnessService.recoveredBy("cron_skipped", NOW, null), "台账里没这个数据集");
        assertFalse(IngestFreshnessService.recoveredBy("cron_skipped", null,
                new IngestFreshnessService.Landed(NOW, NOW)), "create_time 为空时无从比较");
        assertFalse(IngestFreshnessService.recoveredBy("cron_failed", NOW,
                new IngestFreshnessService.Landed(NOW.plusDays(1), null)), "只有 partial 不算 success");
    }
}
