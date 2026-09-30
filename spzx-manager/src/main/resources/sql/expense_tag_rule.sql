-- 费用自动打标规则表（对账管理）
--
-- 背景：expense_order 有 1922 笔账单，expense_tag 有 8 个标签，但 expense_order_tag 一行都没有
-- ——「标签管理」和「按标签统计」两页因此全是空的。人工一笔笔点不现实，需要一个规则引擎
-- 把支付宝已经给出的「交易分类」(counterparty) 批量映射成本地标签。
--
-- 设计取舍：
-- - 一条规则 = 一个字段 + 一种匹配方式 + 一个关键词，可选金额区间。规则表本身很小（几十行），
--   不建二级索引：驱动侧永远是「遍历账单 × 逐条规则比对」，不是按 tag_id 反查。
-- - 命中多条规则就打多个标签（expense_order_tag 是 (order_id, tag_id) 联合主键，天然支持多标）。
--   不做「优先第一条命中」，因为分类映射本就是一对一，标题规则又各自覆盖不同费用性质。
-- - 规则只新增关联，从不删除关联：人工打过、改过的标签不会被下一次自动跑批抹掉。

CREATE TABLE IF NOT EXISTS expense_tag_rule (
    id          BIGINT        NOT NULL AUTO_INCREMENT,
    tag_id      BIGINT        NOT NULL COMMENT '命中后打上的标签，引用 expense_tag.id',
    match_field VARCHAR(16)   NOT NULL DEFAULT 'counterparty' COMMENT '比对字段：counterparty|title|remark|channel',
    match_type  VARCHAR(8)    NOT NULL DEFAULT 'eq' COMMENT 'eq=全等(忽略首尾空格)，like=包含(不区分大小写)',
    keyword     VARCHAR(128)  NOT NULL COMMENT '比对关键词',
    min_amount  DECIMAL(12, 2) NULL COMMENT '金额下限（含），空=不限',
    max_amount  DECIMAL(12, 2) NULL COMMENT '金额上限（含），空=不限',
    status      TINYINT       NOT NULL DEFAULT 1 COMMENT '1=启用 0=停用',
    create_time DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_rule (tag_id, match_field, match_type, keyword)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci COMMENT ='账单自动打标规则';
-- 排序规则必须跟 expense_order / expense_tag 一致（general_ci）：
-- 留默认值的 0900_ai_ci 会让「规则关键词 = 账单分类」这类跨表比较直接报 Illegal mix of collations。

-- 种子规则：把支付宝交易分类逐项映射到已有的 8 个标签。
-- 用标签名反查 tag_id，不写死 id，标签被删重建后重跑本文件仍然正确。
INSERT IGNORE INTO expense_tag_rule (tag_id, match_field, match_type, keyword, status)
SELECT t.id, 'counterparty', 'eq', m.keyword, 1
FROM (SELECT '购物' tag_name, '服饰装扮' keyword
      UNION ALL SELECT '购物', '日用百货'
      UNION ALL SELECT '购物', '数码电器'
      UNION ALL SELECT '购物', '家居家装'
      UNION ALL SELECT '购物', '美容美发'
      UNION ALL SELECT '购物', '运动户外'
      UNION ALL SELECT '饮食', '餐饮美食'
      UNION ALL SELECT '交通', '交通出行'
      UNION ALL SELECT '交通', '爱车养车'
      UNION ALL SELECT '通讯', '充值缴费'
      UNION ALL SELECT '医疗', '医疗健康'
      UNION ALL SELECT '娱乐', '文化休闲'
      UNION ALL SELECT '娱乐', '酒店旅游') m
         JOIN expense_tag t ON t.name = m.tag_name;

-- 自检：规则数、覆盖到的分类、以及「分类里还没被任何规则覆盖」的漏网值
SELECT COUNT(*) AS rule_rows, COUNT(DISTINCT tag_id) AS tags_used FROM expense_tag_rule;

SELECT e.counterparty, COUNT(*) AS bills, IFNULL(r.id, 0) AS covered_by_rule
FROM expense_order e
         LEFT JOIN expense_tag_rule r
                   ON r.status = 1 AND r.match_field = 'counterparty' AND r.match_type = 'eq'
                       AND r.keyword = e.counterparty
GROUP BY e.counterparty, IFNULL(r.id, 0)
ORDER BY bills DESC;
