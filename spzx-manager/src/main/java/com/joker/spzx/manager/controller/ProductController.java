package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.common.util.CsvExportUtil;
import com.joker.spzx.manager.service.ProductService;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.enums.PlatformTypeEnum;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.product.ProductPageVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.PrintWriter;
import java.util.List;

/**
 * <p>
 * 商品 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@RestController
@Tag(name = "货源商品", description = "货源商品管理")
@RequestMapping(value = "/admin/product/sourceProduct")
public class ProductController {
    @Autowired
    private ProductService productService;

    @GetMapping(value = "/pageList")
    public Result<IPage<ProductPageVo>> findByPage(ProductDto productDto) {
        IPage<ProductPageVo> pageInfo = productService.findByPage(productDto);
        return Result.build(pageInfo, ResultCodeEnum.SUCCESS);
    }

    @PostMapping("/saveData")
    public Result<String> save(@Valid @RequestBody Product product) {
        productService.saveData(product);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @PutMapping("/updateData")
    public Result<String> updateById(@Valid @RequestBody Product product) {
        productService.updateDataById(product);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }

    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@Parameter(name = "id", description = "商品id", required = true) @PathVariable Long id) {
        productService.deleteData(id);
        return Result.build(null, ResultCodeEnum.SUCCESS);
    }


    @GetMapping("/getDetail")
    public Result<ProductPageVo> getDetail(@RequestParam Long id) {
        ProductPageVo byId = productService.getDataById(id);
        return Result.build(byId, ResultCodeEnum.SUCCESS);
    }

    @Operation(summary = "查询所有货源商品")
    @GetMapping("/all")
    public Result<List<Product>> listAll() {
        List<Product> list = productService.list();
        return Result.build(list, ResultCodeEnum.SUCCESS);
    }

    @Operation(summary = "导出货源商品CSV")
    @GetMapping("/export")
    public void export(ProductDto productDto, HttpServletResponse response) {
        // 分页插件 maxLimit=500 会静默截断超大 pageSize，导出改为 500/页循环拉全量
        productDto.setPageSize(500);
        List<ProductPageVo> list = new java.util.ArrayList<>();
        for (int pageNum = 1; ; pageNum++) {
            productDto.setPageNum(pageNum);
            List<ProductPageVo> records = productService.findByPage(productDto).getRecords();
            list.addAll(records);
            if (records.size() < 500) {
                break;
            }
        }
        try {
            PrintWriter writer = CsvExportUtil.writeCsvHeaders(response, "货源商品");
            writer.println("商品标题,厂商,商品ID,类目,平台,等级,供应商,货源价格,运费,销量,回头率%,诚信通年限,抓取时间");
            for (ProductPageVo p : list) {
                String platformName = PlatformTypeEnum.nameOf(p.getPlatformType());
                writer.println(String.join(",",
                        CsvExportUtil.escapeCsv(p.getSourceProductName()),
                        CsvExportUtil.escapeCsv(p.getProductFactoryName()),
                        CsvExportUtil.escapeCsv(p.getSourceProductCode()),
                        CsvExportUtil.escapeCsv(p.getCategoryName()),
                        platformName,
                        CsvExportUtil.escapeCsv(p.getQualityGrade()),
                        CsvExportUtil.escapeCsv(p.getSupplierName()),
                        p.getSourcePrice() == null ? "" : String.valueOf(p.getSourcePrice()),
                        p.getFreightCost() == null ? "" : String.valueOf(p.getFreightCost()),
                        p.getSalesCount() == null ? "" : String.valueOf(p.getSalesCount()),
                        p.getRepurchaseRate() == null ? "" : String.valueOf(p.getRepurchaseRate()),
                        p.getTrustYears() == null ? "" : String.valueOf(p.getTrustYears()),
                        p.getCrawlTime() == null ? "" : String.valueOf(p.getCrawlTime())));
            }
            writer.flush();
        } catch (Exception e) {
            throw new RuntimeException("导出CSV异常", e);
        }
    }
}
