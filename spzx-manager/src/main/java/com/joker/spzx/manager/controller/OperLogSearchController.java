package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.OperLogSearchService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
@RequestMapping("/admin/log")
public class OperLogSearchController {

    @Autowired
    private OperLogSearchService operLogSearchService;

    @GetMapping("/search")
    public Result<List<Map<String, Object>>> search(
            @RequestParam(required = false) String operName,
            @RequestParam(required = false) String title,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        List<Map<String, Object>> list = operLogSearchService.search(operName, title, page, size);
        return Result.build(list, ResultCodeEnum.SUCCESS);
    }
}