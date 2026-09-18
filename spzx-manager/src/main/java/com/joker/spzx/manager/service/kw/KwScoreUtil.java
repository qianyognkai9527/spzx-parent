package com.joker.spzx.manager.service.kw;

import com.joker.spzx.manager.config.KwProperties;

import java.util.List;

public final class KwScoreUtil {

    private KwScoreUtil() {
    }

    /**
     * 批内 min-max 归一化加权。
     * rows 每行: [popularity, clickRate, convRate, buyerCount]
     * 买家数维度取 1/(n+1)：买家数少=竞争小=得分高。
     * 返回与 rows 等长的得分数组（0-1）。
     */
    public static double[] score(List<double[]> rows, KwProperties.Weights w) {
        int n = rows.size();
        double[] out = new double[n];
        if (n == 0) {
            return out;
        }
        double[] pop = new double[n];
        double[] click = new double[n];
        double[] conv = new double[n];
        double[] buyerInv = new double[n];
        for (int i = 0; i < n; i++) {
            double[] r = rows.get(i);
            pop[i] = r[0];
            click[i] = r[1];
            conv[i] = r[2];
            buyerInv[i] = 1.0 / (r[3] + 1.0);
        }
        for (int i = 0; i < n; i++) {
            out[i] = w.getPopularity() * norm(pop[i], min(pop), max(pop))
                    + w.getClickRate() * norm(click[i], min(click), max(click))
                    + w.getConvRate() * norm(conv[i], min(conv), max(conv))
                    + w.getBuyer() * norm(buyerInv[i], min(buyerInv), max(buyerInv));
        }
        return out;
    }

    private static double norm(double v, double min, double max) {
        return max > min ? (v - min) / (max - min) : 0.5;
    }

    private static double min(double[] a) {
        double m = Double.MAX_VALUE;
        for (double v : a) {
            m = Math.min(m, v);
        }
        return m;
    }

    private static double max(double[] a) {
        double m = -Double.MAX_VALUE;
        for (double v : a) {
            m = Math.max(m, v);
        }
        return m;
    }
}
