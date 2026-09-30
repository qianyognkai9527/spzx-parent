package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.model.entity.kw.KwProvider;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/config")
public class KwConfigController {

    @Autowired
    private KwConfigService kwConfigService;

    @Autowired
    private KwProviderService kwProviderService;

    /** 引擎键均可选；传了才改（老前端只传 textProvider，兼容）。videoDailyBudget 同理：空串=清除预算 */
    public record SetDto(String textProvider, String visionProvider, String videoProvider,
                         String videoDailyBudget) {
    }

    @GetMapping
    public Result<Map<String, Object>> get() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("textProvider", kwConfigService.getProvider(KwConfigService.KEY_TEXT));
        out.put("visionProvider", kwConfigService.getProvider(KwConfigService.KEY_VISION));
        out.put("videoProvider", kwConfigService.getProvider(KwConfigService.KEY_VIDEO));
        out.put("videoDailyBudget", kwConfigService.getValue(KwConfigService.KEY_VIDEO_BUDGET));
        List<Map<String, Object>> providers = new ArrayList<>();
        for (KwProvider row : kwProviderService.listAll()) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("name", row.getName());
            boolean hasKey = row.getApiKey() != null && !row.getApiKey().isBlank();
            p.put("hasKey", hasKey);
            p.put("keyTail", hasKey
                    ? row.getApiKey().substring(Math.max(0, row.getApiKey().length() - 4)) : "");
            p.put("visionModel", row.getVisionModel());
            p.put("textModel", row.getTextModel());
            p.put("videoModel", row.getVideoModel());
            p.put("videoPrice", row.getVideoPrice());
            p.put("status", row.getStatus());
            providers.add(p);
        }
        out.put("providers", providers);
        return Result.build(out);
    }

    @PutMapping
    public Result<Void> set(@RequestBody SetDto dto) {
        if (dto.textProvider() != null) {
            String err = validateForSwitch(dto.textProvider(), "text");
            if (err != null) {
                return Result.build(null, 204, err);
            }
            kwConfigService.setProvider(KwConfigService.KEY_TEXT, dto.textProvider());
        }
        if (dto.visionProvider() != null) {
            String err = validateForSwitch(dto.visionProvider(), "vision");
            if (err != null) {
                return Result.build(null, 204, err);
            }
            kwConfigService.setProvider(KwConfigService.KEY_VISION, dto.visionProvider());
        }
        if (dto.videoProvider() != null) {
            String err = validateForSwitch(dto.videoProvider(), "video");
            if (err != null) {
                return Result.build(null, 204, err);
            }
            kwConfigService.setProvider(KwConfigService.KEY_VIDEO, dto.videoProvider());
        }
        if (dto.videoDailyBudget() != null) {
            String raw = dto.videoDailyBudget().trim();
            if (raw.isEmpty()) {
                kwConfigService.setValue(KwConfigService.KEY_VIDEO_BUDGET, "");
            } else {
                if (com.joker.spzx.manager.util.VideoPricing.parse(raw) == null) {
                    return Result.build(null, 204, "视频日预算必须是不小于 0 的数字（元），留空=不限制");
                }
                kwConfigService.setValue(KwConfigService.KEY_VIDEO_BUDGET, raw);
            }
        }
        return Result.build(null);
    }

    /** 切换校验：存在 + 启用 + 有 key + kind 对应模型已配 */
    private String validateForSwitch(String name, String kind) {
        KwProvider row = kwProviderService.getEntity(name);
        if (row == null) {
            return "provider 不存在: " + name;
        }
        if (row.getStatus() == null || row.getStatus() != 1) {
            return "provider 已停用: " + name;
        }
        if (row.getApiKey() == null || row.getApiKey().isBlank()) {
            return "provider 未配置 key: " + name;
        }
        String model = KwProviderService.modelOf(row, kind);
        if (model == null || model.isBlank()) {
            return "provider " + name + " 未配置 " + kind + " 模型，请先在 AI引擎配置 页补全";
        }
        return null;
    }
}
