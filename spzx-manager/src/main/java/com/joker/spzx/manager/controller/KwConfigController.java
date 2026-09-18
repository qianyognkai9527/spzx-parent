package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.service.kw.KwConfigService;
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
    private KwProperties props;

    public record SetDto(String textProvider) {
    }

    @GetMapping
    public Result<Map<String, Object>> get() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("textProvider", kwConfigService.getProvider(KwConfigService.KEY_TEXT));
        out.put("visionProvider", kwConfigService.getProvider(KwConfigService.KEY_VISION));
        List<Map<String, Object>> providers = new ArrayList<>();
        for (Map.Entry<String, KwProperties.Provider> e : props.getProviders().entrySet()) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("name", e.getKey());
            p.put("hasKey", e.getValue().getApiKey() != null && !e.getValue().getApiKey().isBlank());
            p.put("visionModel", e.getValue().getVisionModel());
            p.put("textModel", e.getValue().getTextModel());
            providers.add(p);
        }
        out.put("providers", providers);
        return Result.build(out);
    }

    @PutMapping
    public Result<Void> set(@RequestBody SetDto dto) {
        String name = dto.textProvider();
        KwProperties.Provider p = props.getProviders().get(name);
        if (p == null || p.getApiKey() == null || p.getApiKey().isBlank()) {
            return Result.build(null, 204, "provider 不存在或 key 未配置: " + name);
        }
        kwConfigService.setProvider(KwConfigService.KEY_TEXT, name);
        return Result.build(null);
    }
}
