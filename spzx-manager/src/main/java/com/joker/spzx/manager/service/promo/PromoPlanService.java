package com.joker.spzx.manager.service.promo;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.joker.spzx.manager.mapper.PromoPlanMapper;
import com.joker.spzx.manager.mapper.ShopMapper;
import com.joker.spzx.model.entity.platform.Platform;
import com.joker.spzx.model.entity.platform.Shop;
import com.joker.spzx.model.entity.promo.PromoPlan;
import com.joker.spzx.manager.mapper.PlatformMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 推广计划主档维护（写入路径）。
 *
 * 分工：效果数据由 automation/tb-auto/collect_alimama_promo.py 每天写 promo_cost_*_daily，
 * 本服务只管「计划是什么」。两边靠 campaign_id 对得上，谁也不复制谁。
 *
 * 更新走**整行覆盖**（不是 shop 那种「null=不改」的 merge）：这张表一半的列是可选的
 * （预算、时段、负责人），编辑时必须能把一个填错的值清空，
 * 而「留空=不改」会让清空这件事没有入口。列表页的开关按钮因此也走整行 PUT，不另开端点。
 */
@Service
public class PromoPlanService {

    /**
     * 与 promo_cost_daily.plan_type 同枚举，别在这里发明第六种。
     * 用 List 不用 Set：报错文案要把这四个按固定顺序念出来，Set.of 的顺序是哈希顺序。
     */
    public static final List<String> PLAN_TYPES = List.of("keyword", "crowd", "site", "other");

    @Autowired
    private PromoPlanMapper promoPlanMapper;

    @Autowired
    private PlatformMapper platformMapper;

    @Autowired
    private ShopMapper shopMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /**
     * 维护视图。onlineStatus 传 -1 表示「只看未确认的」（库里那一档是 NULL）——
     * Integer 参数区分不了"没传"和"传了 null"，所以未确认用一个显式哨兵，前端下拉里也这么写。
     */
    public List<PromoPlan> listForManage(Integer platformCode, Long shopId, String planType,
                                         Integer onlineStatus, String keyword) {
        String kw = keyword == null || keyword.isBlank() ? null : keyword.trim();
        return promoPlanMapper.selectList(Wrappers.<PromoPlan>lambdaQuery()
                .eq(platformCode != null, PromoPlan::getPlatformCode, platformCode)
                .eq(shopId != null, PromoPlan::getShopId, shopId)
                .eq(planType != null && !planType.isBlank(), PromoPlan::getPlanType, planType)
                .eq(onlineStatus != null && onlineStatus >= 0, PromoPlan::getOnlineStatus, onlineStatus)
                .isNull(Integer.valueOf(-1).equals(onlineStatus), PromoPlan::getOnlineStatus)
                .and(kw != null, w -> w.like(PromoPlan::getCampaignName, kw)
                        .or().like(PromoPlan::getCampaignId, kw)
                        .or().like(PromoPlan::getOwner, kw))
                .orderByAsc(PromoPlan::getPlatformCode)
                .orderByDesc(PromoPlan::getId));
    }

    public PromoPlan getById(Long id) {
        return promoPlanMapper.selectById(id);
    }

    public void savePlan(PromoPlan plan) {
        promoPlanMapper.insert(plan);
    }

    public void updatePlan(PromoPlan plan) {
        promoPlanMapper.updateById(plan);
    }

    public void removePlan(Long id) {
        promoPlanMapper.deleteById(id);
    }

    /** 同店铺同平台下 campaign_id 只能有一条主档；editingId 非空时排除自身 */
    public String campaignConflict(PromoPlan plan, Long editingId) {
        Long hit = promoPlanMapper.selectCount(Wrappers.<PromoPlan>lambdaQuery()
                .eq(PromoPlan::getPlatformCode, plan.getPlatformCode())
                .eq(PromoPlan::getShopId, plan.getShopId())
                .eq(PromoPlan::getCampaignId, plan.getCampaignId())
                .ne(editingId != null, PromoPlan::getId, editingId));
        return hit != null && hit > 0
                ? "该店铺下已存在计划 id " + plan.getCampaignId() + " 的主档" : null;
    }

    /**
     * 不碰库的那半截校验，单独留成静态方法好脱库单测（本仓库的测试一律不拉 Spring 上下文）。
     * 只校验我们自己定的口径（枚举、区间、日期先后）；平台侧的 bidType 取值域我们说了不算，
     * 因此只限长度不限枚举 —— 采集回来一个新值不该把人挡在录入页外。
     */
    public static String checkFields(PromoPlan plan) {
        if (plan.getCampaignId() == null || plan.getCampaignId().isBlank()) {
            return "计划 id 不能为空，它要和采集回来的花费数据对得上";
        }
        plan.setCampaignId(plan.getCampaignId().trim());
        if (plan.getCampaignId().length() > 64) {
            return "计划 id 最长 64 个字符";
        }
        if (plan.getCampaignName() == null || plan.getCampaignName().isBlank()) {
            return "计划名称不能为空";
        }
        plan.setCampaignName(plan.getCampaignName().trim());
        if (plan.getCampaignName().length() > 255) {
            return "计划名称最长 255 个字符";
        }
        if (plan.getShopId() == null) {
            plan.setShopId(0L);
        }
        if (plan.getPlanType() == null || plan.getPlanType().isBlank()) {
            return "必须选择计划类型";
        }
        String planType = plan.getPlanType().trim().toLowerCase();
        if (!PLAN_TYPES.contains(planType)) {
            return "计划类型只能是 " + String.join(" / ", PLAN_TYPES);
        }
        plan.setPlanType(planType);
        if (plan.getBidType() != null) {
            String bidType = plan.getBidType().trim().toLowerCase();
            if (bidType.isEmpty()) {
                plan.setBidType(null);
            } else {
                if (bidType.length() > 24) {
                    return "出价方式最长 24 个字符";
                }
                plan.setBidType(bidType);
            }
        }
        String err = checkMoney(plan.getDailyBudget(), "日预算", true);
        if (err != null) {
            return err;
        }
        err = checkMoney(plan.getBidPrice(), "出价基准", false);
        if (err != null) {
            return err;
        }
        if (plan.getPremiumPercent() != null
                && (plan.getPremiumPercent() < 0 || plan.getPremiumPercent() > 1000)) {
            return "人群溢价应在 0-1000（百分数）之间，+30% 填 30";
        }
        if (plan.getOnlineStatus() != null
                && plan.getOnlineStatus() != 0 && plan.getOnlineStatus() != 1) {
            return "投放状态只有 在投/停投/未确认 三种";
        }
        if (plan.getStartDate() != null && plan.getEndDate() != null
                && plan.getStartDate().isAfter(plan.getEndDate())) {
            return "开始日期不能晚于结束日期";
        }
        err = checkLength(plan.getTimeDiscount(), 64, "分时折扣");
        if (err != null) {
            return err;
        }
        err = checkLength(plan.getOwner(), 32, "负责人");
        if (err != null) {
            return err;
        }
        err = checkLength(plan.getRemark(), 500, "备注");
        if (err != null) {
            return err;
        }
        if (plan.getSource() == null || plan.getSource().isBlank()) {
            plan.setSource("manual");
        }
        return null;
    }

    /** 校验并归一化，返回 null 表示通过，否则是给用户看的错误文案 */
    public String validate(PromoPlan plan) {
        if (plan == null) {
            return "参数为空";
        }
        String fieldErr = checkFields(plan);
        if (fieldErr != null) {
            return fieldErr;
        }
        if (plan.getPlatformCode() == null) {
            return "必须选择所属平台";
        }
        Long knownPlatform = platformMapper.selectCount(Wrappers.<Platform>lambdaQuery()
                .eq(Platform::getCode, plan.getPlatformCode()));
        if (knownPlatform == null || knownPlatform == 0) {
            return "平台编码 " + plan.getPlatformCode() + " 不在平台注册表里";
        }
        if (plan.getShopId() != 0L) {
            Shop shop = shopMapper.selectById(plan.getShopId());
            if (shop == null) {
                return "店铺 id " + plan.getShopId() + " 不存在；不确定就选「未指定」";
            }
            if (!shop.getPlatformCode().equals(plan.getPlatformCode())) {
                return "店铺「" + shop.getShopName() + "」属于平台 " + shop.getPlatformCode()
                        + "，和这条计划的平台不一致";
            }
        }
        return null;
    }

    private static String checkMoney(BigDecimal value, String label, boolean zeroOk) {
        if (value == null) {
            return null;
        }
        if (zeroOk ? value.signum() < 0 : value.signum() <= 0) {
            return label + (zeroOk ? "不能为负数" : "必须大于 0");
        }
        if (value.precision() - value.scale() > 8) {
            return label + "最大 99999999.99 元";
        }
        return null;
    }

    private static String checkLength(String value, int max, String label) {
        return value != null && value.trim().length() > max ? label + "最长 " + max + " 个字符" : null;
    }

    /** 这条计划有多少条已采集的花费数据 —— 删除前用来判断会不会留下孤儿数据 */
    public Map<String, Long> usage(PromoPlan plan) {
        Map<String, Long> out = new LinkedHashMap<>();
        if (plan == null) {
            out.put("daily", 0L);
            out.put("itemDaily", 0L);
            return out;
        }
        out.put("daily", countCost("promo_cost_daily", plan));
        out.put("itemDaily", countCost("promo_cost_item_daily", plan));
        return out;
    }

    public long totalUsage(PromoPlan plan) {
        return usage(plan).values().stream().mapToLong(Long::longValue).sum();
    }

    private long countCost(String table, PromoPlan plan) {
        Long v = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM " + table
                        + " WHERE platform_code = ? AND shop_id = ? AND campaign_id = ?",
                Long.class, plan.getPlatformCode(), plan.getShopId(), plan.getCampaignId());
        return v == null ? 0L : v;
    }
}
