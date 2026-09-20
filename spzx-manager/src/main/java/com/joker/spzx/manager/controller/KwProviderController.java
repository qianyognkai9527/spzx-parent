package com.joker.spzx.manager.controller;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.mapper.KwProviderMapper;
import com.joker.spzx.manager.mapper.KwSelectTaskMapper;
import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.model.entity.kw.KwProvider;
import com.joker.spzx.model.entity.kw.KwSelectTask;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/provider")
public class KwProviderController {

    @Autowired
    private KwProviderMapper kwProviderMapper;

    @Autowired
    private KwSelectTaskMapper kwSelectTaskMapper;

    @Autowired
    private KwProviderService kwProviderService;

    @Autowired
    private KwConfigService kwConfigService;

    /** name 唯一标识；编辑时 name 不可改；apiKey 为空/缺失 = 保留原值 */
    public record SaveDto(String name, String baseUrl, String apiKey,
                          String visionModel, String textModel, String imageModel,
                          Integer maxTokens, String extraBody, String remark) {
    }

    /** 全量列表；apiKey 不回传，只回 hasKey + keyTail(尾4位) */
    @GetMapping("/list")
    public Result<List<Map<String, Object>>> list() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (KwProvider row : kwProviderService.listAll()) {
            out.add(toMap(row));
        }
        return Result.build(out);
    }

    @PostMapping
    public Result<Void> save(@RequestBody SaveDto dto) {
        if (dto.name() == null || dto.name().isBlank()) {
            return Result.build(null, 204, "name 不能为空");
        }
        String name = dto.name().trim();
        if (dto.baseUrl() == null || dto.baseUrl().isBlank()) {
            return Result.build(null, 204, "base_url 不能为空");
        }
        if (kwProviderService.getEntity(name) != null) {
            return Result.build(null, 204, "name 已存在: " + name);
        }
        String extraErr = extraBodyError(dto.extraBody());
        if (extraErr != null) {
            return Result.build(null, 204, extraErr);
        }
        KwProvider row = new KwProvider();
        applyDto(row, dto, null);
        row.setStatus(1);
        kwProviderMapper.insert(row);
        return Result.build(null);
    }

    @PutMapping
    public Result<Void> update(@RequestBody SaveDto dto) {
        if (dto.name() == null || dto.name().isBlank()) {
            return Result.build(null, 204, "name 不能为空");
        }
        KwProvider row = kwProviderService.getEntity(dto.name().trim());
        if (row == null) {
            return Result.build(null, 204, "provider 不存在: " + dto.name());
        }
        String extraErr = extraBodyError(dto.extraBody());
        if (extraErr != null) {
            return Result.build(null, 204, extraErr);
        }
        applyDto(row, dto, row.getApiKey());
        LambdaUpdateWrapper<KwProvider> uw = new LambdaUpdateWrapper<KwProvider>()
                .eq(KwProvider::getId, row.getId())
                .set(KwProvider::getBaseUrl, row.getBaseUrl())
                .set(KwProvider::getApiKey, row.getApiKey())
                .set(KwProvider::getVisionModel, row.getVisionModel())
                .set(KwProvider::getTextModel, row.getTextModel())
                .set(KwProvider::getImageModel, row.getImageModel())
                .set(KwProvider::getMaxTokens, row.getMaxTokens())
                .set(KwProvider::getExtraBody, row.getExtraBody())
                .set(KwProvider::getRemark, row.getRemark());
        kwProviderMapper.update(null, uw);
        return Result.build(null);
    }

    @PutMapping("/status/{id}/{status}")
    public Result<Void> status(@PathVariable Long id, @PathVariable Integer status) {
        if (status == null || (status != 0 && status != 1)) {
            return Result.build(null, 204, "status 只能是 0 或 1");
        }
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        if (status == 0) {
            String err = mainEngineGuard(row.getName(), "停用");
            if (err != null) {
                return Result.build(null, 204, err);
            }
            err = inFlightTaskGuard(row.getName());
            if (err != null) {
                return Result.build(null, 204, err);
            }
        }
        row.setStatus(status);
        kwProviderMapper.updateById(row);
        return Result.build(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        String err = mainEngineGuard(row.getName(), "删除");
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = inFlightTaskGuard(row.getName());
        if (err != null) {
            return Result.build(null, 204, err);
        }
        kwProviderMapper.deleteById(id);
        return Result.build(null);
    }

    /** 连通测试：优先 textModel、无则 visionModel，都无→报错；max_tokens=16 单轮 ping；返回 {ok, costMs, error}，不落库 */
    @PostMapping("/test/{id}")
    public Result<Map<String, Object>> test(@PathVariable Long id) {
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        String model = row.getTextModel() != null && !row.getTextModel().isBlank()
                ? row.getTextModel() : row.getVisionModel();
        if (row.getBaseUrl() == null || row.getBaseUrl().isBlank()
                || row.getApiKey() == null || row.getApiKey().isBlank() || model == null || model.isBlank()) {
            out.put("ok", false);
            out.put("costMs", 0);
            out.put("error", "base_url / api_key / text或vision模型 未配全，无法测试");
            return Result.build(out);
        }
        JSONObject body = new JSONObject();
        body.set("model", model);
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", "ping");
        messages.add(msg);
        body.set("messages", messages);
        body.set("max_tokens", 16);
        if (row.getExtraBody() != null && !row.getExtraBody().isBlank()) {
            try {
                JSONUtil.parseObj(row.getExtraBody()).forEach(body::set);
            } catch (Exception ignored) {
            }
        }
        long start = System.currentTimeMillis();
        try {
            String resp = HttpRequest.post(row.getBaseUrl() + "/chat/completions")
                    .header("Authorization", "Bearer " + row.getApiKey())
                    .header("Content-Type", "application/json")
                    .body(body.toString())
                    .timeout(60000)
                    .execute()
                    .body();
            long costMs = System.currentTimeMillis() - start;
            JSONObject respJson = JSONUtil.parseObj(resp);
            if (respJson.containsKey("error")) {
                out.put("ok", false);
                out.put("costMs", costMs);
                out.put("error", respJson.getJSONObject("error").getStr("message", ""));
            } else if (respJson.containsKey("choices")) {
                out.put("ok", true);
                out.put("costMs", costMs);
                out.put("error", "");
            } else {
                out.put("ok", false);
                out.put("costMs", costMs);
                out.put("error", "响应无 choices: " + resp);
            }
        } catch (Exception e) {
            out.put("ok", false);
            out.put("costMs", System.currentTimeMillis() - start);
            out.put("error", e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
        }
        return Result.build(out);
    }

    /** 当前主用（text/vision 任一命中）→ 返回拒绝消息，否则 null */
    private String mainEngineGuard(String name, String action) {
        if (name.equals(kwConfigService.getProvider(KwConfigService.KEY_TEXT))) {
            return "「" + name + "」是当前文本主用引擎，请先切换后再" + action;
        }
        if (name.equals(kwConfigService.getProvider(KwConfigService.KEY_VISION))) {
            return "「" + name + "」是当前视觉主用引擎，请先切换后再" + action;
        }
        return null;
    }

    /** 在途（待跑/识品中/选词中）任务按 name 快照引用 → 返回拒绝消息，否则 null */
    private String inFlightTaskGuard(String name) {
        Long cnt = kwSelectTaskMapper.selectCount(new LambdaQueryWrapper<KwSelectTask>()
                .eq(KwSelectTask::getTextProvider, name)
                .in(KwSelectTask::getStatus, 0, 1, 2));
        if (cnt != null && cnt > 0) {
            return "有 " + cnt + " 个在途选词任务引用「" + name + "」，等任务完成或失败后再停用/删除";
        }
        return null;
    }

    /** name 不可改（按 name 定位行后仅更新可变字段）；apiKey 空 = 保留原值 */
    private void applyDto(KwProvider row, SaveDto dto, String oldKey) {
        row.setName(dto.name().trim());
        row.setBaseUrl(dto.baseUrl().trim());
        String key = dto.apiKey() == null || dto.apiKey().isBlank() ? oldKey : dto.apiKey().trim();
        row.setApiKey(key == null ? "" : key);
        row.setVisionModel(blankToNull(dto.visionModel()));
        row.setTextModel(blankToNull(dto.textModel()));
        row.setImageModel(blankToNull(dto.imageModel()));
        row.setMaxTokens(dto.maxTokens());
        row.setExtraBody(dto.extraBody() == null || dto.extraBody().isBlank()
                ? null : dto.extraBody().trim());
        row.setRemark(dto.remark());
    }

    private String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }

    /** 非空时必须是合法 JSON 对象，否则返回错误消息 */
    private String extraBodyError(String extraBody) {
        if (extraBody == null || extraBody.isBlank()) {
            return null;
        }
        try {
            JSONUtil.parseObj(extraBody);
            return null;
        } catch (Exception e) {
            return "extra_body 必须是合法 JSON 对象，如 {\"thinking\":{\"type\":\"disabled\"}}";
        }
    }

    private Map<String, Object> toMap(KwProvider row) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("id", row.getId());
        p.put("name", row.getName());
        p.put("baseUrl", row.getBaseUrl());
        p.put("visionModel", row.getVisionModel());
        p.put("textModel", row.getTextModel());
        p.put("imageModel", row.getImageModel());
        p.put("maxTokens", row.getMaxTokens());
        boolean hasKey = row.getApiKey() != null && !row.getApiKey().isBlank();
        p.put("hasKey", hasKey);
        p.put("keyTail", hasKey
                ? row.getApiKey().substring(Math.max(0, row.getApiKey().length() - 4)) : "");
        p.put("status", row.getStatus());
        p.put("remark", row.getRemark());
        p.put("extraBody", row.getExtraBody());
        p.put("updateTime", row.getUpdateTime());
        return p;
    }
}
