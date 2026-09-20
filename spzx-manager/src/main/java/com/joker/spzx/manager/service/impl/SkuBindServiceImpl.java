package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SkuBindRelationMapper;
import com.joker.spzx.manager.service.SkuBindService;
import com.joker.spzx.model.entity.inventory.SkuBindRelation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class SkuBindServiceImpl extends ServiceImpl<SkuBindRelationMapper, SkuBindRelation> implements SkuBindService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Override
    public List<Map<String, Object>> findBindList(Integer pageNum, Integer pageSize, Integer platformType, Integer status) {
        StringBuilder sql = new StringBuilder();
        List<Object> params = new ArrayList<>();
        sql.append("SELECT r.id, r.platform_sku_id AS platformSkuId, r.source_sku_id AS sourceSkuId, r.status, r.match_type AS matchType, r.confirm_by AS confirmBy, r.confirm_time AS confirmTime, ");
        sql.append("ps.sku_key AS platformSkuKey, ");
        sql.append("ss.sku_key AS sourceSkuKey, ss.stock AS sourceStock, ss.price AS sourcePrice, ");
        sql.append("pp.title AS platformProductTitle, ");
        sql.append("sp.source_product_name AS sourceProductName, ");
        sql.append("ps.platform_type AS platformType ");
        sql.append("FROM sku_bind_relation r ");
        sql.append("LEFT JOIN platform_sku ps ON ps.id = r.platform_sku_id ");
        sql.append("LEFT JOIN source_sku ss ON ss.id = r.source_sku_id ");
        sql.append("LEFT JOIN platform_product pp ON pp.id = ps.platform_product_id ");
        sql.append("LEFT JOIN source_product sp ON sp.id = ss.source_product_id ");
        sql.append("WHERE r.is_deleted = 0 ");
        appendWhere(sql, params, platformType, status);
        sql.append("ORDER BY r.update_time DESC ");
        sql.append("LIMIT ?, ?");
        int offset = (pageNum - 1) * pageSize;
        params.add(offset);
        params.add(pageSize);
        return jdbcTemplate.queryForList(sql.toString(), params.toArray());
    }

    @Override
    public long findBindCount(Integer platformType, Integer status) {
        StringBuilder sql = new StringBuilder();
        List<Object> params = new ArrayList<>();
        sql.append("SELECT COUNT(*) FROM sku_bind_relation r ");
        sql.append("LEFT JOIN platform_sku ps ON ps.id = r.platform_sku_id ");
        sql.append("WHERE r.is_deleted = 0 ");
        appendWhere(sql, params, platformType, status);
        Long count = jdbcTemplate.queryForObject(sql.toString(), Long.class, params.toArray());
        return count != null ? count : 0L;
    }

    private void appendWhere(StringBuilder sql, List<Object> params, Integer platformType, Integer status) {
        if (platformType != null) {
            sql.append("AND ps.platform_type = ? ");
            params.add(platformType);
        }
        if (status != null) {
            sql.append("AND r.status = ? ");
            params.add(status);
        }
    }

    @Override
    public Map<String, Object> getOverview() {
        String sql = "SELECT " +
                "(SELECT COUNT(DISTINCT platform_product_id) FROM platform_sku WHERE is_deleted = 0) AS totalProducts, " +
                "(SELECT COUNT(*) FROM sku_bind_relation WHERE is_deleted = 0 AND status = 1) AS confirmedSku, " +
                "(SELECT COUNT(*) FROM sku_bind_relation WHERE is_deleted = 0 AND status = 0) AS pendingSku, " +
                "(SELECT COUNT(*) FROM sku_bind_relation WHERE is_deleted = 0 AND status = 2) AS mismatchSku";
        List<Map<String, Object>> list = jdbcTemplate.queryForList(sql);
        return list.isEmpty() ? new HashMap<>() : list.get(0);
    }

    @Override
    public boolean confirm(Long id) {
        return update(new LambdaUpdateWrapper<SkuBindRelation>()
                .eq(SkuBindRelation::getId, id)
                .eq(SkuBindRelation::getIsDeleted, 0)
                .set(SkuBindRelation::getStatus, 1)
                .set(SkuBindRelation::getConfirmTime, new Date()));
    }

    @Override
    public boolean mismatch(Long id) {
        return update(new LambdaUpdateWrapper<SkuBindRelation>()
                .eq(SkuBindRelation::getId, id)
                .eq(SkuBindRelation::getIsDeleted, 0)
                .set(SkuBindRelation::getStatus, 2));
    }

    @Override
    public boolean rebind(Long id, Long sourceSkuId) {
        return update(new LambdaUpdateWrapper<SkuBindRelation>()
                .eq(SkuBindRelation::getId, id)
                .eq(SkuBindRelation::getIsDeleted, 0)
                .set(SkuBindRelation::getSourceSkuId, sourceSkuId)
                .set(SkuBindRelation::getStatus, 1)
                .set(SkuBindRelation::getMatchType, "manual"));
    }
}
