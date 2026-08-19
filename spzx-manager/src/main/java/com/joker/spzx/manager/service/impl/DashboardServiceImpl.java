package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.mapper.DashboardMapper;
import com.joker.spzx.manager.service.DashboardService;
import com.joker.spzx.manager.service.TaskProgressService;
import com.joker.spzx.model.vo.dashboard.*;
import com.joker.spzx.model.vo.taskprogress.TaskItemVo;
import com.joker.spzx.model.vo.taskprogress.TaskOverviewVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 仪表盘服务实现
 *
 * @author joker
 */
@Service
public class DashboardServiceImpl implements DashboardService {

    @Autowired
    private DashboardMapper dashboardMapper;

    @Autowired
    private TaskProgressService taskProgressService;

    @Override
    public DashboardKpiVo getKpiCards() {
        DashboardKpiVo vo = new DashboardKpiVo();
        vo.setOrderCount(dashboardMapper.countOrders());
        vo.setOrderTotalAmount(dashboardMapper.sumOrderAmount());
        vo.setFactoryCount(dashboardMapper.countFactories());
        vo.setProductCount(dashboardMapper.countProducts());
        return vo;
    }

    @Override
    public List<OrderTrendVo> getOrderTrend() {
        return dashboardMapper.selectOrderTrend();
    }

    @Override
    public List<PlatformDistVo> getPlatformDistribution() {
        List<PlatformDistVo> list = dashboardMapper.selectPlatformDist();
        for (PlatformDistVo vo : list) {
            if (vo.getPlatformType() != null && vo.getPlatformType() == 1) {
                vo.setPlatformName("淘宝");
            } else if (vo.getPlatformType() != null && vo.getPlatformType() == 2) {
                vo.setPlatformName("抖音");
            } else {
                vo.setPlatformName("未分类");
            }
        }
        return list;
    }

    @Override
    public List<TopFactoryVo> getTopFactories() {
        return dashboardMapper.selectTopFactories();
    }

    @Override
    public List<RecentLogVo> getRecentLogs() {
        return dashboardMapper.selectRecentLogs();
    }

    @Override
    public List<java.util.Map<String, Object>> getWatermarkProducts() {
        return dashboardMapper.selectWatermarkProducts();
    }

    @Override
    public List<Map<String, Object>> getTaskAnomalies() {
        List<Map<String, Object>> result = new ArrayList<>();
        try {
            TaskOverviewVo overview = taskProgressService.getOverview();
            if (overview == null || overview.getTasks() == null) {
                return result;
            }
            for (TaskItemVo t : overview.getTasks()) {
                int failed = t.getFailed() != null ? t.getFailed() : 0;
                if (failed <= 0) continue;
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("taskKey", t.getKey());
                m.put("taskName", t.getName());
                m.put("failed", failed);
                m.put("processed", t.getProcessed());
                m.put("saved", t.getSaved());
                m.put("lastLog", t.getLastLog());
                m.put("status", t.getStatus());
                m.put("tags", t.getTags() != null ? t.getTags() : new ArrayList<String>());
                // 按任务类型提取具体异常明细
                m.put("items", buildAnomalyItems(t.getKey()));
                result.add(m);
            }
        } catch (Exception e) {
            // 任务进度服务异常时静默, 首页不阻塞
        }
        return result;
    }

    /** 根据任务 key 从进度文件提取具体异常明细 (分组: 原因 -> 数量 + 商品ID示例) */
    private List<Map<String, Object>> buildAnomalyItems(String taskKey) {
        List<Map<String, Object>> groups = new ArrayList<>();
        switch (taskKey) {
            case "taobao_puhuo": {
                Map<String, List<String>> byError = new LinkedHashMap<>();
                Object failed = readJsonFileField("/Users/qyk9527/tb-auto/progress.json", "failed");
                boolean hasTitle = false;
                if (failed instanceof List<?> list) {
                    for (Object o : list) {
                        if (o instanceof Map<?, ?> fm) {
                            String err = String.valueOf(fm.get("error"));
                            String human = humanizeError(err);
                            String id = String.valueOf(fm.get("id"));
                            Object title = fm.get("title");
                            if (title != null && !String.valueOf(title).isEmpty()) {
                                hasTitle = true;
                                // 有标题则用标题定位(前30字), 便于识别
                                String t = String.valueOf(title);
                                id = t.length() > 30 ? t.substring(0, 30) : t;
                            }
                            byError.computeIfAbsent(human, k -> new ArrayList<>()).add(id);
                        }
                    }
                }
                if (!byError.isEmpty()) {
                    if (hasTitle) {
                        appendGroups(groups, byError);
                    } else {
                        // ISV 铺货日志已清空, 这些 ID 是 ISV 内部行号, 已无法定位到具体商品 -> 标记失效
                        Map<String, Object> g = new LinkedHashMap<>();
                        int total = 0;
                        for (List<String> v : byError.values()) total += v.size();
                        g.put("reason", "铺货失败（ISV日志已清空，商品无法定位）");
                        g.put("count", -1);
                        g.put("ids", new ArrayList<>());
                        g.put("total", -1);
                        g.put("unlocatable", true);
                        groups.add(g);
                    }
                }
                break;
            }
            case "guiruo_douyin":
            case "meijia_douyin": {
                String path = "meijia_douyin".equals(taskKey)
                        ? "/Users/qyk9527/sourcing/output/meijia/progress.json"
                        : "/Users/qyk9527/sourcing/douyin_create_progress.json";
                Map<String, List<String>> byError = new LinkedHashMap<>();
                Object created = readJsonFileField(path, "created");
                if (created instanceof Map<?, ?> map) {
                    for (Map.Entry<?, ?> e : map.entrySet()) {
                        if (e.getValue() instanceof Map<?, ?> v) {
                            String status = String.valueOf(v.get("status"));
                            if (status.contains("fail") || status.contains("error") || status.contains("risk")) {
                                String reason = "create_failed".equals(status)
                                        ? "创建草稿失败" : status;
                                byError.computeIfAbsent(reason, k -> new ArrayList<>())
                                        .add(String.valueOf(e.getKey()));
                            }
                        }
                    }
                }
                appendGroups(groups, byError);
                break;
            }
            case "sourcing_crawl": {
                Object failedKw = readJsonFileField("/Users/qyk9527/sourcing/sourcing_progress.json", "failed_kw");
                if (failedKw instanceof List<?> list && !list.isEmpty()) {
                    Map<String, Object> g = new LinkedHashMap<>();
                    g.put("reason", "风控/超时未采集的关键词");
                    g.put("count", list.size());
                    List<String> ids = new ArrayList<>();
                    for (Object o : list) ids.add(String.valueOf(o));
                    g.put("ids", ids);
                    g.put("total", list.size());
                    groups.add(g);
                }
                break;
            }
            case "freight_fetch": {
                Map<String, Object> g = new LinkedHashMap<>();
                g.put("reason", "运费未抓取（待补抓）");
                g.put("count", -1);
                g.put("ids", new ArrayList<>());
                g.put("total", -1);
                groups.add(g);
                break;
            }
            default:
                break;
        }
        return groups;
    }

    private void appendGroups(List<Map<String, Object>> groups, Map<String, List<String>> byError) {
        for (Map.Entry<String, List<String>> e : byError.entrySet()) {
            Map<String, Object> g = new LinkedHashMap<>();
            g.put("reason", e.getKey());
            g.put("count", e.getValue().size());
            // 展示前若干 ID, 其余折叠
            List<String> ids = e.getValue().size() > 12
                    ? e.getValue().subList(0, 12) : e.getValue();
            g.put("ids", ids);
            g.put("total", e.getValue().size());
            groups.add(g);
        }
    }

    /** 把淘宝铺货原始错误翻译为人话 */
    private String humanizeError(String raw) {
        if (raw == null) return "未知原因";
        String e = raw.trim();
        if (e.startsWith("异常: ")) e = e.substring(4);
        if (e.contains("滑块验证") || e.contains("captcha")) {
            return "触发滑块/验证码风控";
        }
        if (e.contains("无店铺草稿") || e.contains("category.htm")) {
            return "该商品未生成店铺草稿";
        }
        if (e.contains("Locator.click: Timeout") || e.contains("Timeout 30000ms exceeded")) {
            return "页面点击超时（页面未加载/元素未出现）";
        }
        if (e.contains("Locator.input_value") || e.contains("Locator.fill")) {
            return "表单填写超时（输入框未就绪）";
        }
        if (e.contains("Locator.count") || e.contains("Target page, context or browser has been closed")) {
            return "页面被关闭或浏览器异常";
        }
        if (e.contains("Target crashed")) {
            return "页面崩溃（Chrome 内存不足）";
        }
        if (e.contains("总库存必填") || e.contains("宝贝数量") || e.contains("库存")) {
            return "总库存未填写";
        }
        if (e.contains("宝贝销售规格必填")) {
            return "销售规格（SKU）未填写完整";
        }
        if (e.contains("图文描述") || e.contains("主图多视图")) {
            return "主图/详情图不完整（缺多视图）";
        }
        if (e.contains("无法打开编辑页面")) {
            return "无法打开编辑页面";
        }
        if (e.contains("编辑页面处理失败")) {
            return "编辑页面处理失败";
        }
        if (e.contains("未找到提交按钮")) {
            return "未找到提交按钮";
        }
        if (e.contains("提交结果不确定")) {
            return "提交结果不确定（可能已提交）";
        }
        if (e.contains("校验错误数")) {
            int n = e.matches(".*校验错误数: (\\d+).*")
                    ? Integer.parseInt(e.replaceAll(".*校验错误数: (\\d+).*", "$1")) : 0;
            return "商品校验未通过（" + n + " 处错误）";
        }
        if (e.contains("成人") || e.contains("专营") || e.contains("准入")) {
            return "类目准入/资质不符";
        }
        if (e.contains("已下架") || e.contains("商品不存在")) {
            return "商品已下架或不存在";
        }
        if (e.length() > 40) e = e.substring(0, 40);
        return e;
    }

    private Object readJsonFileField(String path, String field) {
        try {
            String content = Files.readString(Path.of(path), StandardCharsets.UTF_8);
            cn.hutool.json.JSONObject obj = cn.hutool.json.JSONUtil.parseObj(content);
            return obj.get(field);
        } catch (Exception e) {
            return null;
        }
    }
}
