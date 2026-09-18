package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/product")
public class KwProductController {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @GetMapping("/list/{pageNum}/{pageSize}")
    public Result<Page<Map<String, Object>>> list(@PathVariable long pageNum,
                                                  @PathVariable long pageSize,
                                                  @RequestParam(required = false) String keyword,
                                                  @RequestParam(required = false) Integer platformType) {
        StringBuilder where = new StringBuilder("WHERE 1=1");
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND title LIKE '%").append(keyword.replace("'", "''")).append("%'");
        }
        if (platformType != null) {
            where.append(" AND platform_type=").append(platformType);
        }
        long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM platform_product " + where, Long.class);
        long offset = (pageNum - 1) * pageSize;
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT p.id, p.code, p.title, p.pricing, p.platform_type platformType, "
                        + "(SELECT m.file_url FROM product_media m WHERE m.product_id=p.id "
                        + "  AND m.file_type=1 ORDER BY m.img_pos LIMIT 1) imgUrl "
                        + "FROM platform_product p " + where
                        + " ORDER BY p.id DESC LIMIT " + pageSize + " OFFSET " + offset);
        Page<Map<String, Object>> p = new Page<>(pageNum, pageSize, total);
        p.setRecords(records);
        return Result.build(p);
    }

    @GetMapping("/{id}/images")
    public Result<List<String>> images(@PathVariable Long id) {
        List<String> urls = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                        + "ORDER BY img_pos LIMIT 5", String.class, id);
        return Result.build(urls);
    }
}
