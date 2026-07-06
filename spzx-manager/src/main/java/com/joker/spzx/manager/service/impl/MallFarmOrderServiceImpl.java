package com.joker.spzx.manager.service.impl;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.excel.SecondOrderExcelBo;
import com.joker.spzx.manager.mapper.MallFarmOrderMapper;
import com.joker.spzx.manager.mapper.MallOrderResourceMapper;
import com.joker.spzx.manager.mapper.MallProductPicVideoMapper;
import com.joker.spzx.manager.service.MallFarmOrderService;
import com.joker.spzx.model.dto.mall.FarmOrderPageDto;
import com.joker.spzx.model.dto.mall.OrderEvaluation;
import com.joker.spzx.model.entity.oper.MallFarmOrder;
import com.joker.spzx.model.entity.oper.MallOrderResource;
import com.joker.spzx.model.entity.oper.MallProductPicVideo;
import com.joker.spzx.model.vo.mall.OderAllocationVo;
import com.joker.spzx.utils.AuthContextUtil;
import com.joker.spzx.utils.excel.DefaultExcelListener;
import com.joker.spzx.utils.excel.ExcelResult;
import com.joker.spzx.utils.excel.ExcelUtil;
import jakarta.servlet.http.HttpServletResponse;
import lombok.SneakyThrows;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * <p>
 * 补单表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-06 17:21:06
 */
@Slf4j
@Service
public class MallFarmOrderServiceImpl extends ServiceImpl<MallFarmOrderMapper, MallFarmOrder> implements MallFarmOrderService {


    @Autowired
    private MallOrderResourceMapper mallOrderResourceMapper;

    @Autowired
    private MallProductPicVideoMapper mallProductPicVideoMapper;

    @Autowired
    private MallFarmOrderMapper mallFarmOrderMapper;

    @Override
    public IPage<MallFarmOrder> findByPage(FarmOrderPageDto farmOrderPageDto) {


        IPage<MallFarmOrder> page = new Page<>(farmOrderPageDto.getPageNum(), farmOrderPageDto.getPageSize());
        LambdaQueryWrapper<MallFarmOrder> eq = lambdaQuery().getWrapper()
                .eq(farmOrderPageDto.getPlatformType() != null, MallFarmOrder::getPlatformType, farmOrderPageDto.getPlatformType())
                .eq(MallFarmOrder::getProductId, farmOrderPageDto.getProductId())
                .eq(Objects.nonNull(farmOrderPageDto.getStatus()), MallFarmOrder::getStatus, farmOrderPageDto.getStatus());
        page(page, eq);
        return page;
    }

    @Override
    public void saveData(MallFarmOrder farmOrderPageDto) {
        farmOrderPageDto.setCreateTime(LocalDateTime.now());
        farmOrderPageDto.setCreateBy(AuthContextUtil.getUser().getId());

        farmOrderPageDto.insert();
    }

    @Override
    public void updateData(MallFarmOrder farmOrderPageDto) {
        farmOrderPageDto.setUpdateBy(AuthContextUtil.getUser().getId());
        farmOrderPageDto.setUpdateTime(LocalDateTime.now());
        farmOrderPageDto.updateById();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void allocateResources(OderAllocationVo oderAllocationVo) {
        Long orderId = oderAllocationVo.getOrderId();
        MallFarmOrder order = mallFarmOrderMapper.selectById(orderId);
        Long productId = order.getProductId();

        LambdaQueryWrapper<MallOrderResource> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallOrderResource::getOrderId, oderAllocationVo.getOrderId());
        Long count = mallOrderResourceMapper.selectCount(lambdaQueryWrapper);
        if (count > 0) {
            mallOrderResourceMapper.delete(lambdaQueryWrapper);
        }
        List<Long> resourceIds = oderAllocationVo.getResourceIds();
        List<MallOrderResource> collect = resourceIds.stream().map(resourceId -> {
            return new MallOrderResource() {{
                setOrderId(orderId);
                setFileId(resourceId);
            }};
        }).collect(Collectors.toList());
        mallOrderResourceMapper.insert(collect);
        LambdaUpdateWrapper<MallProductPicVideo> lambdaUpdateWrapper = new LambdaUpdateWrapper<>();
        lambdaUpdateWrapper.eq(MallProductPicVideo::getProductId, productId)
                .in(MallProductPicVideo::getId, resourceIds)
                .set(MallProductPicVideo::getState, 1);
        mallProductPicVideoMapper.update(lambdaUpdateWrapper);

        String comment = oderAllocationVo.getComment();

        MallFarmOrder mallFarmOrder = new MallFarmOrder();
        mallFarmOrder.setId(orderId);
        mallFarmOrder.setCommentStatus(2);//已分配买家秀
        if (StringUtils.isNotBlank(comment)) {
            mallFarmOrder.setComment(comment);
        }

        mallFarmOrder.setUpdateTime(LocalDateTime.now());
        mallFarmOrder.setUpdateBy(AuthContextUtil.getUser().getId());
        mallFarmOrder.updateById();

    }

    @SneakyThrows
    @Override
    public void gennerShowBuy(List<Long> orderIdList, HttpServletResponse response) {
        // 批量查询优化：将 N+1 查询改为 3 次批量查询
        // 1. 批量获取所有农场订单
        List<MallFarmOrder> farmOrders = this.listByIds(orderIdList);
        Map<Long, MallFarmOrder> farmOrderMap = farmOrders.stream()
                .collect(Collectors.toMap(MallFarmOrder::getId, f -> f));

        // 2. 批量获取所有订单资源关联
        LambdaQueryWrapper<MallOrderResource> resourceWrapper = new LambdaQueryWrapper<MallOrderResource>()
                .in(MallOrderResource::getOrderId, orderIdList);
        List<MallOrderResource> allResources = mallOrderResourceMapper.selectList(resourceWrapper);
        Map<Long, List<MallOrderResource>> resourceByOrderId = allResources.stream()
                .collect(Collectors.groupingBy(MallOrderResource::getOrderId));

        // 3. 批量获取所有图片视频
        Set<Long> allFileIds = allResources.stream()
                .map(MallOrderResource::getFileId)
                .collect(Collectors.toSet());
        Map<Long, String> fileUrlMap = java.util.Collections.emptyMap();
        if (CollectionUtils.isNotEmpty(allFileIds)) {
            List<MallProductPicVideo> allPicVideos = mallProductPicVideoMapper.selectList(
                    new LambdaQueryWrapper<MallProductPicVideo>().in(MallProductPicVideo::getId, allFileIds));
            fileUrlMap = allPicVideos.stream()
                    .collect(Collectors.toMap(MallProductPicVideo::getId, MallProductPicVideo::getFileUrl));
        }

        // 内存组装结果
        final Map<Long, String> finalFileUrlMap = fileUrlMap;
        List<OrderEvaluation> evaluations = orderIdList.stream().map(oderId -> {
            MallFarmOrder mallFarmOrder = farmOrderMap.get(oderId);
            OrderEvaluation orderEvaluation = new OrderEvaluation();
            orderEvaluation.setOrderId(mallFarmOrder.getTbOrderCode());
            orderEvaluation.setComment(mallFarmOrder.getComment());
            List<MallOrderResource> resources = resourceByOrderId.get(oderId);
            if (CollectionUtils.isNotEmpty(resources)) {
                List<String> fileUrls = resources.stream()
                        .map(r -> finalFileUrlMap.get(r.getFileId()))
                        .filter(Objects::nonNull)
                        .collect(Collectors.toList());
                orderEvaluation.setFileUrls(fileUrls);
            }
            return orderEvaluation;
        }).collect(Collectors.toList());
        //本地下载
//        this.createEvaluationArchive(evaluations,"");

// 设置浏览器下载头
        response.setContentType("application/zip");

        response.addHeader("Content-Disposition", "attachment;fileName=" + URLEncoder.encode("order_comment", StandardCharsets.UTF_8));
        response.addHeader("Content-Type", "application/octet-stream");
// 直接获取输出流
        OutputStream outputStream = response.getOutputStream();
        try (ZipOutputStream zos = new ZipOutputStream(outputStream)) {
            for (OrderEvaluation eval : evaluations) {
                // 创建订单目录
                String orderDir = eval.getOrderId() + "/";
                zos.putNextEntry(new ZipEntry(orderDir));

                // 写入评语文件
                createCommentFile(zos, orderDir, eval.getComment());

                // 下载媒体文件
                downloadMediaFiles(zos, orderDir, eval.getFileUrls());
            }
            zos.close();
            zos.finish();
        } catch (Exception e) {
            handleException(response, e, outputStream);
        } finally {
            outputStream.close();
        }

    }

    @SneakyThrows
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void importOrderData(MultipartFile file, Map<String, Object> bodyMap) {
        ExcelResult<SecondOrderExcelBo> excelResult = ExcelUtil.importExcel(file.getInputStream(), SecondOrderExcelBo.class, new DefaultExcelListener<>(true));
        if (!excelResult.isSuccess()) {
            List<String> errorList = excelResult.getErrorList();
            throw new ServiceException(202, "数据存在异常：" + errorList);
        }
        MallFarmOrder mallFarmOrder = JSONUtil.toBean(JSONUtil.toJsonStr(bodyMap), MallFarmOrder.class);
        List<SecondOrderExcelBo> list = excelResult.getList();
        Long loginUserId = AuthContextUtil.getUser().getId();
        List<MallFarmOrder> collect = list.stream().map(bo -> {
            MallFarmOrder tmpOrder = new MallFarmOrder();
            BeanUtils.copyProperties(mallFarmOrder, tmpOrder);
            tmpOrder.setTbOrderCode(bo.getOrderId());
            tmpOrder.setCommentStatus(1);
            tmpOrder.setCreateBy(loginUserId);
            tmpOrder.setCreateTime(LocalDateTime.now());
            return tmpOrder;
        }).collect(Collectors.toList());
        this.baseMapper.insert(collect);
    }

    // 主入口
    public void createEvaluationArchive(List<OrderEvaluation> evaluations,
                                        String outputZipPath) throws Exception {
        Path tempDir = Files.createTempDirectory("orders_");

        // 创建所有订单目录和文件
        for (OrderEvaluation eval : evaluations) {
            Path orderDir = createOrderDirectory(tempDir, eval.getOrderId());
            downloadFiles(eval.getFileUrls(), orderDir);
            createCommentFile(eval.getComment(), orderDir);
        }

        // 压缩整个临时目录
        zipFolder(tempDir, Paths.get(outputZipPath));

        // 清理临时文件（可选）
        this.deleteDirectory(tempDir);
    }

    // 创建订单目录
    private Path createOrderDirectory(Path parentDir, String orderId) throws IOException {
        Path orderDir = parentDir.resolve(orderId);
        Files.createDirectories(orderDir);
        return orderDir;
    }

    // 下载文件（支持图片/视频）
    private void downloadFiles(List<String> fileUrls, Path targetDir) {
        fileUrls.forEach(url -> {
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(30000);
                conn.setReadTimeout(60000);
                conn.setRequestProperty("User-Agent", "Mozilla/5.0");

                try (InputStream in = conn.getInputStream()) {
                    String fileName = getFileNameFromUrl(url);
                    Path outputPath = targetDir.resolve(fileName);
                    Files.copy(in, outputPath, StandardCopyOption.REPLACE_EXISTING);
                }
            } catch (Exception e) {
                log.error("下载失败: {} | 错误: {}", url, e.getMessage());
            }
        });
    }

    // 创建评语文件
    private void createCommentFile(String comment, Path orderDir) throws IOException {
        Path commentFile = orderDir.resolve("评语.txt");
        Files.writeString(commentFile, comment, StandardCharsets.UTF_8);
    }

    // 压缩目录（核心方法）
    private void zipFolder(Path sourceDir, Path zipPath) throws IOException {
        try (ZipOutputStream zos = new ZipOutputStream(Files.newOutputStream(zipPath))) {
            Files.walk(sourceDir)
                    .filter(path -> !Files.isDirectory(path))
                    .forEach(path -> {
                        ZipEntry zipEntry = new ZipEntry(sourceDir.relativize(path).toString());
                        try {
                            zos.putNextEntry(zipEntry);
                            Files.copy(path, zos);
                            zos.closeEntry();
                        } catch (IOException e) {
                            log.error("压缩失败: {}", path);
                        }
                    });
        }
    }

    // 从URL提取文件名
    private String getFileNameFromUrl(String fileUrl) {
        return fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
    }

    // 递归删除目录
    private void deleteDirectory(Path directory) throws IOException {
        Files.walk(directory)
                .sorted((a, b) -> -a.compareTo(b))
                .forEach(path -> {
                    try {
                        Files.deleteIfExists(path);
                    } catch (IOException e) {
                        log.error("删除失败: {}", path);
                    }
                });
    }

    private void createCommentFile(ZipOutputStream zos, String orderDir, String comment)
            throws IOException {
        ZipEntry entry = new ZipEntry(orderDir + "评语.txt");
        zos.putNextEntry(entry);
        zos.write(comment.getBytes(StandardCharsets.UTF_8));
        zos.closeEntry();
    }

    private void downloadMediaFiles(ZipOutputStream zos, String orderDir, List<String> urls) {
        urls.forEach(url -> {
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setConnectTimeout(30000);
                conn.setReadTimeout(60000);
                conn.setRequestProperty("User-Agent", "Mozilla/5.0");

                String fileName = getFileName(url);
                ZipEntry entry = new ZipEntry(orderDir + fileName);
                zos.putNextEntry(entry);

                try (InputStream in = conn.getInputStream()) {
                    byte[] buffer = new byte[8192];
                    int bytesRead;
                    while ((bytesRead = in.read(buffer)) != -1) {
                        zos.write(buffer, 0, bytesRead);
                    }
                }
                zos.closeEntry();
            } catch (Exception e) {
                log.error("文件下载失败: {}", url);
            }
        });
    }

    private String getFileName(String url) {
        String rawName = url.substring(url.lastIndexOf('/') + 1);
        return URLEncoder.encode(rawName, StandardCharsets.UTF_8);
    }

    private void handleException(HttpServletResponse response, Exception e, OutputStream outputStream) {
        try {
            outputStream.close();
            response.setContentType("application/json");
            response.setCharacterEncoding("UTF-8");
            response.setStatus(500);
            response.getWriter().write("{\"error\":\"" + e.getMessage() + "\"}");
        } catch (IOException ex) {
            log.error("异常处理失败", ex);
        }
    }
}
