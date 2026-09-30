package com.joker.spzx.manager.service.platform;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.joker.spzx.manager.mapper.PlatformCapabilityMapper;
import com.joker.spzx.manager.mapper.PlatformMapper;
import com.joker.spzx.manager.mapper.ShopMapper;
import com.joker.spzx.model.entity.platform.Platform;
import com.joker.spzx.model.entity.platform.PlatformCapability;
import com.joker.spzx.model.entity.platform.Shop;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 平台/店铺/能力注册表读取服务。
 * P0 只做只读注册表：所有方法直接查库，不做缓存。
 */
@Service
public class PlatformRegistryService {

    @Autowired
    private PlatformMapper platformMapper;

    @Autowired
    private ShopMapper shopMapper;

    @Autowired
    private PlatformCapabilityMapper platformCapabilityMapper;

    /** 全部平台（含停用），按编码升序 */
    public List<Platform> listAll() {
        return platformMapper.selectList(Wrappers.<Platform>lambdaQuery().orderByAsc(Platform::getCode));
    }

    /** 启用中的平台，按编码升序 */
    public List<Platform> listEnabled() {
        return platformMapper.selectList(Wrappers.<Platform>lambdaQuery()
                .eq(Platform::getEnabled, 1)
                .orderByAsc(Platform::getCode));
    }

    /** 启用中的店铺；platformCode 为 null 表示全部平台。凭据引用与本机 CDP 端口不随只读列表外发。 */
    public List<Shop> listShops(Integer platformCode) {
        List<Shop> shops = shopMapper.selectList(Wrappers.<Shop>lambdaQuery()
                .eq(platformCode != null, Shop::getPlatformCode, platformCode)
                .eq(Shop::getStatus, 1)
                .orderByAsc(Shop::getId));
        shops.forEach(PlatformRegistryService::hideInternalFields);
        return shops;
    }

    private static void hideInternalFields(Shop shop) {
        shop.setCredentialRef(null);
        shop.setCdpPort(null);
    }

    /** 某平台的能力集合：capability -> supported==1，按能力名升序 */
    public Map<String, Boolean> capabilities(int platformCode) {
        List<PlatformCapability> rows = platformCapabilityMapper.selectList(
                Wrappers.<PlatformCapability>lambdaQuery()
                        .eq(PlatformCapability::getPlatformCode, platformCode)
                        .orderByAsc(PlatformCapability::getCapability));
        Map<String, Boolean> out = new LinkedHashMap<>();
        for (PlatformCapability row : rows) {
            out.put(row.getCapability(), isSupported(row));
        }
        return out;
    }

    /** 某平台是否具备某项能力 */
    public boolean supports(int platformCode, String capability) {
        if (capability == null || capability.isBlank()) {
            return false;
        }
        PlatformCapability row = platformCapabilityMapper.selectOne(
                Wrappers.<PlatformCapability>lambdaQuery()
                        .eq(PlatformCapability::getPlatformCode, platformCode)
                        .eq(PlatformCapability::getCapability, capability)
                        .last("LIMIT 1"));
        return isSupported(row);
    }

    /** 某平台的默认店铺 id；无平台编码或无可用店铺返回 null */
    public Long defaultShopId(Integer platformCode) {
        return pickDefaultShop(listShops(platformCode), platformCode);
    }

    /**
     * 默认店铺选取规则（纯函数，便于脱库脱 Spring 单测）：
     * 1. 只考虑 platformCode 匹配的店铺；
     * 2. 只考虑 status==1 的店铺；
     * 3. 优先取 isDefault==1 的店铺（多个默认时取 id 最小）；
     * 4. 没有默认店铺时取 id 最小的那一个；
     * 5. 入参为空或 platformCode 为 null 时返回 null。
     */
    public static Long pickDefaultShop(List<Shop> shops, Integer platformCode) {
        if (shops == null || shops.isEmpty() || platformCode == null) {
            return null;
        }
        List<Shop> candidates = new ArrayList<>();
        for (Shop shop : shops) {
            if (shop == null || shop.getId() == null) {
                continue;
            }
            if (!platformCode.equals(shop.getPlatformCode())) {
                continue;
            }
            if (shop.getStatus() == null || shop.getStatus() != 1) {
                continue;
            }
            candidates.add(shop);
        }
        if (candidates.isEmpty()) {
            return null;
        }
        Shop preferred = null;
        for (Shop shop : candidates) {
            if (shop.getIsDefault() == null || shop.getIsDefault() != 1) {
                continue;
            }
            if (preferred == null || shop.getId() < preferred.getId()) {
                preferred = shop;
            }
        }
        if (preferred != null) {
            return preferred.getId();
        }
        return candidates.stream()
                .map(Shop::getId)
                .min(Comparator.naturalOrder())
                .orElse(null);
    }

    private static boolean isSupported(PlatformCapability row) {
        return row != null && row.getSupported() != null && row.getSupported() == 1;
    }
}
