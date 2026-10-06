package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.common.util.ShellUtil;
import com.joker.spzx.manager.mapper.VisualScoreMapper;
import com.joker.spzx.manager.service.VisualScoreService;
import com.joker.spzx.model.dto.mall.GenerateVariantDto;
import com.joker.spzx.model.dto.mall.RescoreDto;
import com.joker.spzx.model.vo.mall.VisualScoreImgVo;
import com.joker.spzx.model.vo.mall.VisualScoreSourceVo;
import com.joker.spzx.model.vo.mall.VisualScoreStatsVo;
import com.joker.spzx.model.vo.mall.VisualScoreVo;
import com.joker.spzx.model.vo.mall.VariantItemVo;
import com.joker.spzx.model.vo.mall.VariantSetVo;
import com.joker.spzx.utils.GradeUtil;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Slf4j
@Service
public class VisualScoreServiceImpl implements VisualScoreService {

    @Autowired
    private VisualScoreMapper visualScoreMapper;

    @Value("${visual.python-bin:${user.dir}/automation/venv/bin/python}")
    private String pythonBin;

    @Value("${visual.script-dir:${user.dir}/automation/sourcing}")
    private String scriptDir;

    private static final Pattern SCORE_PATTERN = Pattern.compile("SCORE:(\\d+)");
    private static final Pattern SET_PATTERN = Pattern.compile("SET:(\\d+)");
    private static final long SCRIPT_TIMEOUT_SECONDS = 180;

    @Override
    public IPage<VisualScoreVo> pageListPlatform(Integer pageNum, Integer pageSize, Integer platformType,
                                                  String keyword, Integer scoreMin, Integer scoreMax) {
        Page<VisualScoreVo> page = PageQueryUtil.of(pageNum, pageSize);
        IPage<VisualScoreVo> result = visualScoreMapper.pageListPlatform(page, platformType, keyword, scoreMin, scoreMax);
        List<VisualScoreVo> records = result.getRecords();
        if (!records.isEmpty()) {
            List<Long> ids = records.stream().map(VisualScoreVo::getProductId).collect(Collectors.toList());
            List<VisualScoreImgVo> imgs = visualScoreMapper.selectImgs(ids, platformType);
            Map<Long, List<VisualScoreImgVo>> byProduct = new LinkedHashMap<>();
            for (VisualScoreImgVo img : imgs) {
                byProduct.computeIfAbsent(img.getProductId(), k -> new ArrayList<>()).add(img);
            }
            records.forEach(vo -> {
                List<VisualScoreImgVo> list = byProduct.getOrDefault(vo.getProductId(), new ArrayList<>());
                list.forEach(i -> i.setGrade(GradeUtil.toGrade(i.getVisualScore())));
                vo.setImgs(list);
            });
        }
        return result;
    }

    @Override
    public IPage<VisualScoreSourceVo> pageListSource(Integer pageNum, Integer pageSize,
                                                      String keyword, Integer scoreMin, Integer scoreMax) {
        Page<VisualScoreSourceVo> page = PageQueryUtil.of(pageNum, pageSize);
        IPage<VisualScoreSourceVo> result = visualScoreMapper.pageListSource(page, keyword, scoreMin, scoreMax);
        result.getRecords().forEach(vo -> vo.setGrade(GradeUtil.toGrade(vo.getVisualScore())));
        return result;
    }

    @Override
    public VisualScoreStatsVo statsPlatform(Integer platformType) {
        return withStaleness(visualScoreMapper.statsPlatform(platformType));
    }

    @Override
    public VisualScoreStatsVo statsSource() {
        return withStaleness(visualScoreMapper.statsSource());
    }

    /**
     * 分数是批量脚本跑出来的、跑完就不再动，接口却和实时数据长一样。
     * 把「最后一次写分距今几天」算出来带上，界面才有得显示"截至"。
     */
    private static VisualScoreStatsVo withStaleness(VisualScoreStatsVo vo) {
        vo.setStaleDays(staleDays(vo.getScoredAt(), LocalDate.now()));
        return vo;
    }

    /** 整天取整；未来时间（时钟偏差）按 0 天算，不返回负数 */
    public static Integer staleDays(LocalDateTime scoredAt, LocalDate today) {
        if (scoredAt == null) {
            return null;
        }
        return (int) Math.max(ChronoUnit.DAYS.between(scoredAt.toLocalDate(), today), 0);
    }

    @Override
    public Integer rescore(RescoreDto dto) {
        String script;
        String arg;
        if ("platform".equals(dto.getType())) {
            script = scriptDir + "/assess_main_img.py";
            arg = "--media-id";
        } else if ("source".equals(dto.getType())) {
            script = scriptDir + "/assess_visual.py";
            arg = "--id";
        } else {
            throw new ServiceException(500, "无效的 rescore type: " + dto.getType());
        }
        String output = runScript(script, arg, String.valueOf(dto.getId()));
        Matcher m = SCORE_PATTERN.matcher(output);
        if (m.find()) {
            return Integer.parseInt(m.group(1));
        }
        throw new ServiceException(500, "未获取到评分结果: " + output.trim());
    }

    @Override
    public Integer generateVariant(GenerateVariantDto dto) {
        if (dto.getProductId() == null || dto.getPlatformType() == null) {
            throw new ServiceException(400, "productId 和 platformType 不能为空");
        }
        String script = scriptDir + "/generate_main_img_variants.py";
        String output = runScript(script,
                "--product-id", String.valueOf(dto.getProductId()),
                "--platform-type", String.valueOf(dto.getPlatformType()));
        Matcher m = SET_PATTERN.matcher(output);
        if (m.find()) {
            return Integer.parseInt(m.group(1));
        }
        throw new ServiceException(500, "未获取到生成套号: " + output.trim());
    }

    @Override
    public List<VariantSetVo> variantList(Long productId, Integer platformType) {
        if (productId == null) {
            throw new ServiceException(400, "productId 不能为空");
        }
        List<VariantItemVo> items = visualScoreMapper.selectVariants(productId, platformType);
        items.forEach(i -> i.setGrade(GradeUtil.toGrade(i.getVisualScore())));
        Map<Integer, List<VariantItemVo>> grouped = new LinkedHashMap<>();
        for (VariantItemVo item : items) {
            Integer set = item.getVariantSet();
            if (set == null) continue;
            grouped.computeIfAbsent(set, k -> new ArrayList<>()).add(item);
        }
        List<VariantSetVo> result = new ArrayList<>();
        for (Map.Entry<Integer, List<VariantItemVo>> e : grouped.entrySet()) {
            VariantSetVo vo = new VariantSetVo();
            vo.setVariantSet(e.getKey());
            vo.setPlatformType(platformType);
            vo.setItems(e.getValue());
            result.add(vo);
        }
        return result;
    }

    private String runScript(String script, String... args) {
        requireChain(script);
        List<String> cmd = new ArrayList<>();
        cmd.add(pythonBin);
        cmd.add(script);
        for (String a : args) cmd.add(a);
        ShellUtil.ShellResult result = ShellUtil.run(cmd, SCRIPT_TIMEOUT_SECONDS * 1000);
        if (result.timedOut()) {
            throw new ServiceException(500, "脚本执行超时(" + SCRIPT_TIMEOUT_SECONDS + "s): " + script);
        }
        if (result.exitCode() < 0) {
            log.error("视觉评分脚本执行异常: script={}, output={}", script, result.output().trim());
            throw new ServiceException(500, "脚本执行异常");
        }
        String output = result.output();
        if (result.exitCode() != 0) {
            log.error("视觉评分脚本执行失败: script={}, output={}", script, output.trim());
            throw new ServiceException(500, "脚本执行失败");
        }
        return output;
    }

    /**
     * 跑之前先看文件和解释器在不在。2026-10-03 实测：assess_main_img.py / assess_visual.py /
     * generate_main_img_variants.py 已不在 visual.script-dir 里（整批归档进 sourcing/_archive_20260906/），
     * 少了这一步就只剩一句"脚本执行失败"，看不出是链路断了还是图坏了。
     */
    private void requireChain(String script) {
        if (!Files.isRegularFile(Path.of(script))) {
            throw new ServiceException(500, "评分脚本不存在：" + script
                    + "。这条链路依赖配置 visual.script-dir 指向的目录，脚本目前不在那里（已随目录归档），重算不可用。");
        }
        if (!Files.isRegularFile(Path.of(pythonBin))) {
            throw new ServiceException(500, "Python 解释器不存在：" + pythonBin
                    + "（配置项 visual.python-bin）；脚本在，但跑不起来。");
        }
    }
}
