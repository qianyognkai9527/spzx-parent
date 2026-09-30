package com.joker.spzx.manager.task;

import com.joker.spzx.model.entity.inventory.SyncAlert;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

class SyncAlertNotifyTaskTest {

    @Test
    void markdown含消息与商品id() {
        SyncAlert a = new SyncAlert();
        a.setAlertType("STOCK_DOWN");
        a.setMessage("库存 20 → 3");
        a.setPlatformProductId(4722L);
        SyncAlert b = new SyncAlert();
        b.setAlertType("SYNC_FAIL"); // 无 message 时回退类型
        String md = SyncAlertNotifyTask.markdownOf(List.of(a, b));
        assertTrue(md.contains("库存 20 → 3"), md);
        assertTrue(md.contains("（商品 4722）"), md);
        assertTrue(md.contains("SYNC_FAIL"), md);
        assertTrue(md.startsWith("### 运营提醒（2 条）"), md);
    }

    @Test
    void markdown无商品id时不拼括号() {
        SyncAlert a = new SyncAlert();
        a.setMessage("仅消息");
        assertTrue(!SyncAlertNotifyTask.markdownOf(List.of(a)).contains("（商品 "));
    }
}
