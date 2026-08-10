package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.ProductService;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.product.Product;
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

import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
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
        productDto.setPageNum(1);
        productDto.setPageSize(100000);
        List<ProductPageVo> list = productService.findByPage(productDto).getRecords();
        try {
            String fileName = URLEncoder.encode("货源商品", StandardCharsets.UTF_8.name()).replaceAll("\\+", "%20");
            response.setContentType("text/csv;charset=utf-8");
            response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName + ".csv");
            PrintWriter writer = new PrintWriter(new OutputStreamWriter(response.getOutputStream(), StandardCharsets.UTF_8));
            writer.println("商品标题,厂商,商品ID,类目,平台,等级,供应商,货源价格,运费,销量,回头率%,诚信通年限,抓取时间");
            for (ProductPageVo p : list) {
                Integer pt = p.getPlatformType();
                String platformName = pt != null && pt == 2 ? "抖音" : (pt != null && pt == 1 ? "淘宝" : "");
                writer.println(String.join(",",
                        csv(p.getSourceProductName()),
                        csv(p.getProductFactoryName()),
                        csv(p.getSourceProductCode()),
                        csv(p.getCategoryName()),
                        platformName,
                        csv(p.getQualityGrade()),
                        csv(p.getSupplierName()),
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

    private static String csv(Object v) {
        if (v == null) {
            return "";
        }
        String s = v.toString().replace("\"", "\"\"");
        if (s.contains(",") || s.contains("\"") || s.contains("\n")) {
            return "\"" + s + "\"";
        }
        return s;
    }
}
