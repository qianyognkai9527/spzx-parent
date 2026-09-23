package com.joker.spzx.manager.service.videogen;

import com.joker.spzx.manager.service.FileService;
import com.joker.spzx.manager.service.kw.KwAiClient;
import com.joker.spzx.manager.service.kw.KwConfigService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 视频分镜提示词生成：查商品与主图 → 本地图转 base64 组多模态 content → vision 模型 → 解析 JSON。
 */
@Service
public class VideoPromptService {

    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private KwAiClient aiClient;
    @Autowired
    private KwConfigService configService;
    @Autowired
    private FileService fileService;

    public VideoJsonUtil.VideoPromptResult generate(Long productId) {
        // 注：platform_product 表无 is_deleted 列（brief 原 SQL 与库结构不符，仓内 KwTaskService 同表查询均不带软删条件），故不加
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT id, code, title, pricing, platform_type FROM platform_product WHERE id=?", productId);
        List<String> imgs = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 ORDER BY img_pos LIMIT 4",
                String.class, productId);
        List<Map<String, Object>> parts = new ArrayList<>();
        Map<String, Object> text = new LinkedHashMap<>();
        text.put("type", "text");
        text.put("text", PROMPT_TEMPLATE.formatted(
                String.valueOf(product.get("title")), String.valueOf(product.get("pricing"))));
        parts.add(text);
        for (String url : imgs) {
            byte[] bytes = fileService.readBytes(url);           // 本地图转 base64，绕开"外部拉不到 127.0.0.1"
            Map<String, Object> img = new LinkedHashMap<>();
            img.put("type", "image_url");
            img.put("image_url", Map.of("url",
                    "data:image/jpeg;base64," + Base64.getEncoder().encodeToString(bytes)));
            parts.add(img);
        }
        String provider = configService.getProvider(KwConfigService.KEY_VISION);
        String content = aiClient.vision(provider, parts);
        return VideoJsonUtil.parsePromptJson(content);
    }

    private static final String PROMPT_TEMPLATE = """
            你是电商短视频导演。基于商品图和标题，设计一条15秒竖屏带货短视频的首帧图生视频方案。
            商品标题：%s 价格：%s
            输出严格JSON：{"storyboard":[{"shot":1,"sec":2,"desc":"画面","camera":"运镜"}],"prompt":"一段可直接提交视频生成模型的中文画面描述"}
            规则：prompt 描述的是"一张首帧图会动起来"的连续画面，30-150字；主体为商品实物，含人群使用场景与情绪氛围；不描述文字/水印/logo；规避平台违禁词（最/第一/顶级）。只输出JSON。
            """;
}
