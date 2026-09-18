package com.joker.spzx.manager.service.kw;

import com.alibaba.excel.EasyExcel;
import com.alibaba.excel.ExcelWriter;
import com.alibaba.excel.annotation.ExcelProperty;
import com.alibaba.excel.write.metadata.WriteSheet;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.KwTaskWordMapper;
import com.joker.spzx.manager.mapper.KwTitleSuggestionMapper;
import com.joker.spzx.model.entity.kw.KwTaskWord;
import com.joker.spzx.model.entity.kw.KwTitleSuggestion;
import jakarta.servlet.http.HttpServletResponse;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

@Service
public class KwExportService {

    @Autowired
    private KwTaskWordMapper wordMapper;

    @Autowired
    private KwTitleSuggestionMapper titleMapper;

    // EasyExcel 4.0.3 的 BeanMap 无法读取 record 组件值（会产出空单元格），必须用 POJO
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class WordRow {
        @ExcelProperty("关键词")
        private String keyword;
        @ExcelProperty("匹配度")
        private Integer matchScore;
        @ExcelProperty("词表得分")
        private BigDecimal bankScore;
        @ExcelProperty("理由")
        private String reason;
        @ExcelProperty("已勾选")
        private String picked;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TitleRow {
        @ExcelProperty("标题")
        private String title;
        @ExcelProperty("理由")
        private String reason;
    }

    public void export(Long taskId, HttpServletResponse response) throws Exception {
        List<WordRow> words = new ArrayList<>();
        for (KwTaskWord w : wordMapper.selectList(new LambdaQueryWrapper<KwTaskWord>()
                .eq(KwTaskWord::getTaskId, taskId)
                .orderByDesc(KwTaskWord::getMatchScore))) {
            words.add(new WordRow(w.getKeyword(), w.getMatchScore(), w.getBankScore(),
                    w.getReason(), w.getPicked() != null && w.getPicked() == 1 ? "是" : "否"));
        }
        List<TitleRow> titles = new ArrayList<>();
        for (KwTitleSuggestion t : titleMapper.selectList(new LambdaQueryWrapper<KwTitleSuggestion>()
                .eq(KwTitleSuggestion::getTaskId, taskId))) {
            titles.add(new TitleRow(t.getTitle(), t.getReason()));
        }
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("kw_task_" + taskId, StandardCharsets.UTF_8);
        response.setHeader("Content-Disposition", "attachment;filename=" + fileName + ".xlsx");
        try (ExcelWriter writer = EasyExcel.write(response.getOutputStream()).build()) {
            WriteSheet s1 = EasyExcel.writerSheet(0, "匹配词").head(WordRow.class).build();
            WriteSheet s2 = EasyExcel.writerSheet(1, "标题建议").head(TitleRow.class).build();
            writer.write(words, s1);
            writer.write(titles, s2);
        }
    }
}
