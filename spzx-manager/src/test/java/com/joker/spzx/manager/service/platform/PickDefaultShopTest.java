package com.joker.spzx.manager.service.platform;

import com.joker.spzx.model.entity.platform.Shop;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class PickDefaultShopTest {

    private static Shop shop(long id, int platformCode, int status, int isDefault) {
        Shop shop = new Shop();
        shop.setId(id);
        shop.setPlatformCode(platformCode);
        shop.setStatus(status);
        shop.setIsDefault(isDefault);
        return shop;
    }

    @Test
    void 优先取默认店铺() {
        List<Shop> shops = Arrays.asList(
                shop(1L, 1, 1, 0),
                shop(2L, 1, 1, 1),
                shop(3L, 1, 1, 0));
        assertEquals(2L, PlatformRegistryService.pickDefaultShop(shops, 1));
    }

    @Test
    void 多个默认店铺时取id最小() {
        List<Shop> shops = Arrays.asList(shop(9L, 1, 1, 1), shop(4L, 1, 1, 1));
        assertEquals(4L, PlatformRegistryService.pickDefaultShop(shops, 1));
    }

    @Test
    void 无默认店铺时唯一启用店铺兜底() {
        List<Shop> shops = Collections.singletonList(shop(5L, 1, 1, 0));
        assertEquals(5L, PlatformRegistryService.pickDefaultShop(shops, 1));
    }

    @Test
    void 无默认店铺且多个候选时取id最小() {
        List<Shop> shops = Arrays.asList(shop(7L, 1, 1, 0), shop(3L, 1, 1, 0));
        assertEquals(3L, PlatformRegistryService.pickDefaultShop(shops, 1));
    }

    @Test
    void 停用店铺不参与选取() {
        List<Shop> shops = Arrays.asList(
                shop(1L, 1, 0, 1),
                shop(2L, 1, 1, 0),
                shop(3L, 1, 1, 0));
        assertEquals(2L, PlatformRegistryService.pickDefaultShop(shops, 1));
    }

    @Test
    void 忽略其他平台的店铺() {
        List<Shop> shops = Arrays.asList(
                shop(10L, 2, 1, 1),
                shop(11L, 1, 1, 0));
        assertEquals(11L, PlatformRegistryService.pickDefaultShop(shops, 1));
        assertNull(PlatformRegistryService.pickDefaultShop(shops, 3));
    }

    @Test
    void 平台编码为空时返回空() {
        List<Shop> shops = Collections.singletonList(shop(1L, 1, 1, 1));
        assertNull(PlatformRegistryService.pickDefaultShop(shops, null));
    }

    @Test
    void 空列表与null列表返回空() {
        assertNull(PlatformRegistryService.pickDefaultShop(new ArrayList<>(), 1));
        assertNull(PlatformRegistryService.pickDefaultShop(null, 1));
    }
}
