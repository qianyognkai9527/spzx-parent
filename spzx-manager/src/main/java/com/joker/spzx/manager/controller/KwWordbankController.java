package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.kw.KwWordbankService;
import com.joker.spzx.model.entity.kw.KwWordbankBatch;
import com.joker.spzx.model.entity.kw.KwWordbankItem;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/admin/kw/wordbank")
public class KwWordbankController {

    @Autowired
    private KwWordbankService kwWordbankService;

    @PostMapping("/upload")
    public Result<Long> upload(@RequestParam("files") List<MultipartFile> files,
                               @RequestParam("name") String name,
                               @RequestParam(value = "platformType", required = false) Integer platformType) {
        return Result.build(kwWordbankService.upload(files, name, platformType));
    }

    @GetMapping("/batch/list")
    public Result<List<KwWordbankBatch>> batchList() {
        return Result.build(kwWordbankService.batchList());
    }

    @GetMapping("/batch/{batchId}/items/{pageNum}/{pageSize}")
    public Result<IPage<KwWordbankItem>> items(@PathVariable Long batchId,
                                               @PathVariable long pageNum,
                                               @PathVariable long pageSize) {
        return Result.build(kwWordbankService.itemPage(batchId, pageNum, pageSize));
    }
}
