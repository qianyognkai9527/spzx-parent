package com.joker.spzx.manager.service.kw;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;

/**
 * 关键词推广（标准计划）出价链条的算术。
 *
 * 顺序是平台的口径，不是我们能选的：
 * <pre>
 *   最终出价 = 关键词出价 × (1 + 人群溢价%) × 分时折扣%   〔× 全能调价系数，平台自动〕
 * </pre>
 * 三条必须记住的事，都在单元测试里钉着：
 *  1. **人群溢价取最高、不叠加**：同一时刻命中多个人群，只按溢价最高的那个出价。
 *     相加会把上限虚抬高，反推出来的"可承受出价"就敢乱花钱。
 *  2. **全能调价是黑箱**：平台只公布"调价幅度"，不公布按转化概率怎么调。所以这里只输出
 *     区间 {@code [×(1-幅度), ×(1+幅度)]}，不给单点值；反推上限一律用**最坏情况**（+幅度），
 *     否则给出去的关键词出价会在高峰时段直接突破可承受 CPC。
 *  3. **出价是上限不是成本**：实际点击扣费走 GSP（对手出价×对手质量分/我的质量分 + 0.01），
 *     且不超过当时的最终出价。所以 {@link #gspCharge} 只是"按对手估一次扣费"，
 *     真正要回答的运营问题在 {@link #cpcCeilingByFeeRate} / {@link #cpcCeilingByMargin}。
 *
 * 所有百分比参数统一用「30 表示 +30%」的口径，跟后台界面里填的数字一致，
 * 免得出现 0.3 与 30 两套写法互乘的老问题。
 */
public final class KwBidCalculator {

    /** 分时折扣上限 300%（后台最高能设到 300），人群溢价同理 */
    static final double MAX_PCT = 300;
    /** 全能调价幅度是"上下浮动"，100% 就已经是零到双倍，不允许更大 */
    static final double MAX_SWING = 100;

    private KwBidCalculator() {
    }

    public record Crowd(String name, double premiumPct) {
    }

    public record Schedule(String label, double discountPct) {
    }

    /** 一个人群 × 一个时段的出价结果；notServing=true 表示该时段折扣设了 0%，根本不投放 */
    public record Cell(String crowd, String schedule, double certain, double low, double high,
                       double premiumPct, double discountPct, boolean notServing) {
    }

    public record Matrix(List<Cell> cells, double maxHigh) {
    }

    /** 商品运营台一行的效果+毛利数据，用来反推可承受出价 */
    public record ItemInputs(double payAmount, int payBuyers, long visitors,
                             double unitMargin, boolean abnormalTraffic) {
    }

    /** 反推口径：客单价（成交均价）、转化率%、每单毛利 */
    public record Target(double unitPrice, double convRatePct, double unitMargin) {
    }

    public static double withPremium(double baseBid, double premiumPct) {
        require(baseBid, "关键词出价");
        requirePct(premiumPct, "人群溢价");
        return baseBid * (1 + premiumPct / 100);
    }

    public static double withDiscount(double bid, double discountPct) {
        require(bid, "出价");
        requirePct(discountPct, "分时折扣");
        return bid * discountPct / 100;
    }

    /** 不含全能调价的确定值 —— 后台"出价"那一栏真正写的数就是这个 */
    public static double finalBid(double baseBid, double premiumPct, double discountPct) {
        return withDiscount(withPremium(baseBid, premiumPct), discountPct);
    }

    public static double omniHigh(double bid, double swingPct) {
        require(bid, "出价");
        requireSwing(swingPct);
        return bid * (1 + swingPct / 100);
    }

    public static double omniLow(double bid, double swingPct) {
        require(bid, "出价");
        requireSwing(swingPct);
        return Math.max(0, bid * (1 - swingPct / 100));
    }

    /** 命中多个人群时生效的溢价：取最高，不相加 */
    public static double highestPremium(List<Crowd> crowds) {
        double top = 0;
        for (Crowd c : crowds) {
            requirePct(c.premiumPct(), "人群溢价");
            top = Math.max(top, c.premiumPct());
        }
        return top;
    }

    public static boolean notServing(double discountPct) {
        requirePct(discountPct, "分时折扣");
        return discountPct <= 0;
    }

    /**
     * 人群 × 时段的出价矩阵。全能调价作用在整条链的结果上，
     * 所以同一人群在不同时段的区间宽度也不同（折扣越低，绝对幅度越小）。
     */
    public static Matrix matrix(double baseBid, List<Crowd> crowds, List<Schedule> schedules, double swingPct) {
        requireSwing(swingPct);
        List<Cell> cells = new ArrayList<>();
        double maxHigh = 0;
        for (Crowd crowd : crowds) {
            for (Schedule schedule : schedules) {
                double certain = finalBid(baseBid, crowd.premiumPct(), schedule.discountPct());
                double high = money(omniHigh(certain, swingPct));
                double low = notServing(schedule.discountPct()) ? 0 : money(omniLow(certain, swingPct));
                certain = money(certain);
                maxHigh = Math.max(maxHigh, high);
                cells.add(new Cell(crowd.name(), schedule.label(), certain, low, high,
                        crowd.premiumPct(), schedule.discountPct(), notServing(schedule.discountPct())));
            }
        }
        return new Matrix(List.copyOf(cells), maxHigh);
    }

    /**
     * 从商品运营台的一行宝贝推出反推口径：客单价用**成交均价**（成交额/买家数），
     * 不是标价 —— 有优惠券和SKU差价时两者能差三成，按标价算会把上限吹高。
     * 转化率 = 买家数/访客数。
     */
    public static Target targetFromItem(ItemInputs in) {
        if (in.abnormalTraffic()) {
            throw new IllegalArgumentException("该宝贝近7日是平台侧一次性低质流量（访客高、跳失>80%、零成交），"
                    + "访客与转化都不可信，不能用来反推出价上限");
        }
        if (in.visitors() <= 0) {
            throw new IllegalArgumentException("该宝贝没有访客数据（抖店商品未接生意参谋采集），反推不出出价上限；"
                    + "请手工填客单价和转化率");
        }
        double unitPrice = in.payBuyers() > 0 ? money(in.payAmount() / in.payBuyers()) : 0;
        double convRatePct = in.payBuyers() > 0 ? in.payBuyers() * 100.0 / in.visitors() : 0;
        return new Target(unitPrice, convRatePct, in.unitMargin());
    }

    /**
     * 推荐关键词出价：把**实际出价**（这一档真正出出去的价，常拿行业平均出价当目标）当成目标，
     * 反推基数该填多少。
     * 因子与 {@link #maxBaseBid} 同一条：(1+溢价) × 折扣 × (1+全能调价幅度)，
     * 全能调价按最坏情况（+幅度）预留 —— 宁可基数低一点，也别在高峰时段突破目标价。
     *
     * @param targetPct 对标系数：100=跟目标持平，80=压着打，120=抢排名
     */
    public static double recommendedBaseBid(double targetBid, double targetPct,
                                            double premiumPct, double discountPct, double swingPct) {
        require(targetBid, "实际出价");
        requirePct(targetPct, "对标系数");
        return maxBaseBid(targetBid * targetPct / 100, premiumPct, discountPct, swingPct);
    }

    /**
     * 按推广费率口径：每点击最多愿意出多少。
     * 客单价 × 转化率 = 每个访客的期望成交金额；再乘可接受费率 = 每个访客可承受的推广费。
     */
    public static double cpcCeilingByFeeRate(double unitPrice, double convRatePct, double feeRatePct) {
        require(unitPrice, "客单价");
        requireRate(convRatePct, "转化率");
        requireRate(feeRatePct, "可承受推广费率");
        return unitPrice * convRatePct / 100 * feeRatePct / 100;
    }

    /**
     * 按毛利分成口径：每单毛利里愿意拿出来投推广的那部分 × 转化率。
     * 与上面那条互斥使用 —— 有真实毛利率时优先用这条，它不会被运费和退款骗。
     */
    public static double cpcCeilingByMargin(double unitMargin, double convRatePct, double marginSharePct) {
        require(unitMargin, "每单毛利");
        requireRate(convRatePct, "转化率");
        requireRate(marginSharePct, "毛利投入比例");
        return unitMargin * marginSharePct / 100 * convRatePct / 100;
    }

    /**
     * 反推关键词出价上限：给定了 CPC 上限、当前生效的人群溢价、分时折扣，
     * 关键词基数最多能填多少。全能调价一律按最坏情况（+幅度）预留。
     * 该时段折扣为 0 时出多少都没意义，返回 0 而不是除以一个 0。
     */
    public static double maxBaseBid(double cpcCeiling, double premiumPct, double discountPct, double swingPct) {
        require(cpcCeiling, "可承受 CPC 上限");
        requirePct(premiumPct, "人群溢价");
        requirePct(discountPct, "分时折扣");
        requireSwing(swingPct);
        if (discountPct <= 0) {
            return 0;
        }
        double factor = (1 + premiumPct / 100) * (discountPct / 100) * (1 + swingPct / 100);
        return cpcCeiling / factor;
    }

    /**
     * GSP 扣费估计：对手出价×对手质量分/我的质量分 + 0.01，且不超过我方当时的出价上限。
     * 质量分只是"相对高低"的乘数，不是线性可比的分数，这一项请当量级参考，别当账单。
     */
    public static double gspCharge(double rivalBid, double rivalQuality, double myQuality, double myBidCap) {
        require(rivalBid, "对手出价");
        requirePositive(rivalQuality, "对手质量分");
        requirePositive(myQuality, "我的质量分");
        require(myBidCap, "我的出价");
        double raw = rivalBid * rivalQuality / myQuality + 0.01;
        return money(Math.min(raw, myBidCap));
    }

    /**
     * 金额落到分：先修掉浮点毛刺（1.0499999999999998 是 1.05），再**向下**取整。
     * 向下是有意的：出价上限吹高一分钱，就等于给了一个实际会突破可承受成本的数。
     */
    public static double money(double v) {
        require(v, "金额");
        return new BigDecimal(Double.toString(v))
                .setScale(6, RoundingMode.HALF_UP)
                .setScale(2, RoundingMode.FLOOR)
                .doubleValue();
    }

    /**
     * 差额落到分：和 {@link #money} 的区别是**允许负数**（负数表示已经顶破目标价），
     * 且四舍五入而不是向下 —— 它不是上限，只是一个带符号的差值。
     */
    public static double signedMoney(double v) {
        requireFinite(v, "差额");
        return new BigDecimal(Double.toString(v))
                .setScale(6, RoundingMode.HALF_UP)
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
    }

    private static void require(double v, String what) {
        requireFinite(v, what);
        if (v < 0) {
            throw new IllegalArgumentException(what + "不能为负数");
        }
    }

    private static void requireFinite(double v, String what) {
        if (Double.isNaN(v) || Double.isInfinite(v)) {
            throw new IllegalArgumentException(what + "不是有效数字");
        }
    }

    private static void requirePositive(double v, String what) {
        require(v, what);
        if (v <= 0) {
            throw new IllegalArgumentException(what + "必须大于 0");
        }
    }

    private static void requirePct(double v, String what) {
        require(v, what);
        if (v > MAX_PCT) {
            throw new IllegalArgumentException(what + "不能超过 " + (int) MAX_PCT + "%（本工具入参上限，不是平台规则）");
        }
    }

    private static void requireSwing(double v) {
        require(v, "全能调价幅度");
        if (v > MAX_SWING) {
            throw new IllegalArgumentException("全能调价幅度不能超过 " + (int) MAX_SWING + "%");
        }
    }

    private static void requireRate(double v, String what) {
        require(v, what);
        if (v > 100) {
            throw new IllegalArgumentException(what + "不能超过 100%");
        }
    }
}
