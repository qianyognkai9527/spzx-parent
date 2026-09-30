package com.joker.spzx.model.vo.product;

import com.fasterxml.jackson.annotation.JsonFormat;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 1688 货源行情视图：只回读 Python（collect_1688_full.py）已采集入库的数据。
 * Java 不抓 1688——抓取依赖桌面 Chrome 登录态与 CDP 端口分工，属采集侧职责。
 *
 * @param collectedDaysAgo 距最后一次采集的天数，null=该货源行没有更新时间
 * @param stale            采集数据是否已陈旧到不该直接采用
 * @param hint             给操作人的下一步，未采集与已陈旧都走这里，不作为异常
 */
public record Source1688Vo(
        boolean found,
        String offerId,
        Long sourceProductId,
        String title,
        String url,
        BigDecimal sourcePrice,
        BigDecimal freightCost,
        @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime collectedAt,
        Integer collectedDaysAgo,
        boolean stale,
        String hint) {

    /** 库里没有这个 offerId：正常返回，不抛异常，前端据 found=false 提示 */
    public static Source1688Vo notCollected(String offerId, String hint) {
        return new Source1688Vo(false, offerId, null, null, null, null, null, null, null, false, hint);
    }
}
