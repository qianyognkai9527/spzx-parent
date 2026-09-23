package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.videogen.VideoPromptService;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/admin/videogen")
public class VideoGenController {

    @Autowired
    private VideoPromptService promptService;

    @PostMapping("/prompt")
    public Result<Map<String, Object>> prompt(@RequestBody Map<String, Long> body) {
        Long productId = body == null ? null : body.get("productId");
        if (productId == null) return Result.build(null, 204, "请先选择商品");
        try {
            var r = promptService.generate(productId);
            return Result.build(Map.of("storyboard", r.storyboard(), "prompt", r.prompt()));
        } catch (RuntimeException e) { // 覆盖 IAE 与 hutool JSONException（parsePromptJson 畸形括号输入漏 JSONException）
            return Result.build(null, 204, e.getMessage());
        }
    }
}
