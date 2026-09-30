package com.joker.spzx.manager.service.platform;

import com.joker.spzx.model.entity.platform.Shop;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ShopFieldMergeTest {

    private static Shop row() {
        Shop shop = new Shop();
        shop.setId(1L);
        shop.setPlatformCode(1);
        shop.setShopName("淘宝主店");
        shop.setIngestChannel("browser");
        shop.setOuterShopId("TB-001");
        shop.setCredentialRef("alipay-main");
        shop.setCdpPort(9222);
        shop.setFirstOnlineAt(LocalDate.of(2025, 3, 1));
        shop.setIsDefault(1);
        shop.setStatus(1);
        return shop;
    }

    @Test
    void 只切启停不会抹掉凭据引用和CDP端口() {
        Shop patch = new Shop();
        patch.setStatus(0);

        Shop db = row();
        ShopService.mergeEditable(db, patch);

        assertEquals(0, db.getStatus());
        assertEquals("alipay-main", db.getCredentialRef());
        assertEquals(9222, db.getCdpPort());
        assertEquals("TB-001", db.getOuterShopId());
        assertEquals(1, db.getIsDefault());
    }

    @Test
    void 带值的字段逐项覆盖() {
        Shop patch = new Shop();
        patch.setShopName("  改名后的店  ");
        patch.setCdpPort(9224);
        patch.setFirstOnlineAt(LocalDate.of(2026, 1, 1));

        Shop db = row();
        ShopService.mergeEditable(db, patch);

        assertEquals("改名后的店", db.getShopName());
        assertEquals(9224, db.getCdpPort());
        assertEquals(LocalDate.of(2026, 1, 1), db.getFirstOnlineAt());
        assertEquals("alipay-main", db.getCredentialRef());
    }

    @Test
    void 空字符串表示清空该字段() {
        Shop patch = new Shop();
        patch.setCredentialRef("   ");

        Shop db = row();
        ShopService.mergeEditable(db, patch);

        assertEquals("", db.getCredentialRef());
        assertEquals(9222, db.getCdpPort());
    }

    @Test
    void 空白店名不会把原名字冲掉() {
        Shop patch = new Shop();
        patch.setShopName("   ");

        Shop db = row();
        ShopService.mergeEditable(db, patch);

        assertEquals("淘宝主店", db.getShopName());
    }

    @Test
    void 入参为空不动原记录() {
        Shop db = row();
        ShopService.mergeEditable(db, null);
        assertEquals("淘宝主店", db.getShopName());
        assertEquals(9222, db.getCdpPort());
    }
}
