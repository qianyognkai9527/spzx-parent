package com.joker.spzx.manager.service.platform;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.joker.spzx.manager.mapper.PlatformMapper;
import com.joker.spzx.manager.mapper.ShopMapper;
import com.joker.spzx.model.entity.platform.Platform;
import com.joker.spzx.model.entity.platform.Shop;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 店铺维护服务（写入路径）。
 *
 * 与 PlatformRegistryService 的分工：那边是采集/统计用的只读注册表，必须对外隐藏
 * credential_ref 与 cdp_port；这边是店铺管理页的增删改查，要能看到并编辑这两个字段，
 * 所以各自走自己的查询，不共用一个"既隐藏又展示"的方法。
 */
@Service
public class ShopService {

    private static final Set<String> CHANNELS = Set.of("browser", "api", "export");

    @Autowired
    private ShopMapper shopMapper;

    @Autowired
    private PlatformMapper platformMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /** 维护视图：含停用店铺与内部字段，按平台、id 排序 */
    public List<Shop> listForManage(Integer platformCode) {
        return shopMapper.selectList(Wrappers.<Shop>lambdaQuery()
                .eq(platformCode != null, Shop::getPlatformCode, platformCode)
                .orderByAsc(Shop::getPlatformCode)
                .orderByAsc(Shop::getId));
    }

    /**
     * 编辑时只覆盖请求里带了值的字段：文本留空表示"不改"而不是"清空"（清空走单独的置空操作），
     * 这样只切一个启停开关的 PATCH 不会把凭据引用和 CDP 端口抹掉。纯函数，便于脱库单测。
     */
    public static void mergeEditable(Shop row, Shop patch) {
        if (row == null || patch == null) {
            return;
        }
        if (patch.getShopName() != null && !patch.getShopName().isBlank()) {
            row.setShopName(patch.getShopName().trim());
        }
        if (patch.getPlatformCode() != null) {
            row.setPlatformCode(patch.getPlatformCode());
        }
        if (patch.getIngestChannel() != null && !patch.getIngestChannel().isBlank()) {
            row.setIngestChannel(patch.getIngestChannel());
        }
        if (patch.getOuterShopId() != null) {
            row.setOuterShopId(patch.getOuterShopId().trim());
        }
        if (patch.getCredentialRef() != null) {
            row.setCredentialRef(patch.getCredentialRef().trim());
        }
        if (patch.getCdpPort() != null) {
            row.setCdpPort(patch.getCdpPort());
        }
        if (patch.getFirstOnlineAt() != null) {
            row.setFirstOnlineAt(patch.getFirstOnlineAt());
        }
        if (patch.getStatus() != null) {
            row.setStatus(patch.getStatus());
        }
        if (patch.getIsDefault() != null) {
            row.setIsDefault(patch.getIsDefault());
        }
    }

    /** 校验并归一化，返回 null 表示通过，否则是给用户看的错误文案 */
    public String validate(Shop shop) {
        if (shop == null) {
            return "参数为空";
        }
        if (shop.getShopName() == null || shop.getShopName().isBlank()) {
            return "店铺名称不能为空";
        }
        shop.setShopName(shop.getShopName().trim());
        if (shop.getPlatformCode() == null) {
            return "必须选择所属平台";
        }
        Long known = platformMapper.selectCount(Wrappers.<Platform>lambdaQuery()
                .eq(Platform::getCode, shop.getPlatformCode()));
        if (known == null || known == 0) {
            return "平台编码 " + shop.getPlatformCode() + " 不在平台注册表里";
        }
        if (shop.getIngestChannel() != null && !shop.getIngestChannel().isBlank()) {
            String channel = shop.getIngestChannel().trim().toLowerCase();
            if (!CHANNELS.contains(channel)) {
                return "采集通道只能是 " + String.join(" / ", CHANNELS);
            }
            shop.setIngestChannel(channel);
        }
        if (shop.getCdpPort() != null && (shop.getCdpPort() < 1024 || shop.getCdpPort() > 65535)) {
            return "CDP 端口应在 1024-65535 之间";
        }
        // 停用店铺不能占着默认位：采集选默认店时只认 status=1
        if (Integer.valueOf(1).equals(shop.getIsDefault()) && Integer.valueOf(0).equals(shop.getStatus())) {
            return "停用中的店铺不能设为默认店铺";
        }
        return null;
    }

    /** 同平台下重名检查；editingId 非空时排除自身 */
    public String nameConflict(String shopName, Integer platformCode, Long editingId) {
        Long hit = shopMapper.selectCount(Wrappers.<Shop>lambdaQuery()
                .eq(Shop::getPlatformCode, platformCode)
                .eq(Shop::getShopName, shopName)
                .ne(editingId != null, Shop::getId, editingId));
        return hit != null && hit > 0 ? "该平台下已存在同名店铺「" + shopName + "」" : null;
    }

    public Shop getById(Long id) {
        return shopMapper.selectById(id);
    }

    public void saveShop(Shop shop) {
        shopMapper.insert(shop);
    }

    public void updateShop(Shop shop) {
        shopMapper.updateById(shop);
    }

    public void removeShop(Long id) {
        shopMapper.deleteById(id);
    }

    /** 每个平台的默认店铺唯一：把新的置 1 的同时清掉同平台其它默认标记。
     *  否则 defaultShopId 会在两个默认店之间摇摆，采集落到哪个店就不确定了。 */
    @Transactional(rollbackFor = Exception.class)
    public void applyDefaultExclusive(Shop shop) {
        if (!Integer.valueOf(1).equals(shop.getIsDefault())) {
            return;
        }
        shopMapper.update(null, Wrappers.<Shop>lambdaUpdate()
                .set(Shop::getIsDefault, 0)
                .eq(Shop::getPlatformCode, shop.getPlatformCode())
                .eq(Shop::getIsDefault, 1)
                .ne(shop.getId() != null, Shop::getId, shop.getId()));
    }

    public Map<String, Long> usage(Long shopId) {
        Map<String, Long> out = new LinkedHashMap<>();
        out.put("platformProduct", countRef("platform_product", shopId));
        out.put("orderInfo", countRef("order_info", shopId));
        out.put("refund", countRef("refund_import_order", shopId));
        out.put("alert", countRef("sync_alert", shopId));
        return out;
    }

    /** 引用总数：被数据引用过的店铺不提供删除，避免历史数据变成孤儿 */
    public long totalUsage(Long shopId) {
        return usage(shopId).values().stream().mapToLong(Long::longValue).sum();
    }

    private long countRef(String table, Long shopId) {
        Long v = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + table + " WHERE shop_id = ?", Long.class, shopId);
        return v == null ? 0L : v;
    }
}
