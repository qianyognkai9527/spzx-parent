"""优质等级分级脚本(task2)。

给 source_product(仅 data_source=1 1688搜索候选) 和 source_factory(platform_type=1)
计算 quality_grade: 商品 A/B/C, 厂家 A/B, 其余 NULL=未达标。

幂等: 重复执行会用 CASE WHEN 全量重算覆盖。每次抓取/导入后跑一次即可。
用法: automation/venv/bin/python grade_quality.py

台账: crontab 每天 05:30 直调本脚本(没有 bash 包装层), 所以批次由脚本自己写 ingest_batch、
异常由脚本自己写 sync_alert。分级结果被 5 处 Java 读路径当筛选/排序条件
(SalesRankingMapper 直接 quality_grade IN ('A','B')), 静默跑挂会让榜单与看板一起失真。
"""
import pymysql

import cron_alert
from cron_batch import begin_batch, end_batch
from source_config import (
    PRODUCT_GRADE_A, PRODUCT_GRADE_B, PRODUCT_GRADE_C,
    FACTORY_GRADE_A, FACTORY_GRADE_B,
)

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
DATASET = "source_quality_grade"
ALERT_KEY = "grade_quality"


def grade_product(trust, repurchase, sales):
    """商品等级: A>B>C>None。取最高匹配级。"""
    t, r, s = trust or 0, repurchase or 0, sales or 0
    if t >= PRODUCT_GRADE_A["trust"] and r >= PRODUCT_GRADE_A["repurchase"] and s >= PRODUCT_GRADE_A["sales"]:
        return "A"
    if t >= PRODUCT_GRADE_B["trust"] and r >= PRODUCT_GRADE_B["repurchase"] and s >= PRODUCT_GRADE_B["sales"]:
        return "B"
    if t >= PRODUCT_GRADE_C["trust"] and r >= PRODUCT_GRADE_C["repurchase"] and s >= PRODUCT_GRADE_C["sales"]:
        return "C"
    return None


def grade_factory(trust, repurchase, total_sales, product_count):
    """厂家等级: A>B>None。A 是 B 的超集(A=B条件+更严), 保证严格层级。"""
    t, r, ts, pc = trust or 0, repurchase or 0, total_sales or 0, product_count or 0
    if t >= FACTORY_GRADE_A["trust"] and r >= FACTORY_GRADE_A["repurchase"] \
            and ts >= FACTORY_GRADE_A["total_sales"] and pc >= FACTORY_GRADE_A["product_count"]:
        return "A"
    if t >= FACTORY_GRADE_B["trust"] and r >= FACTORY_GRADE_B["repurchase"] and ts >= FACTORY_GRADE_B["total_sales"]:
        return "B"
    return None


# 用常量拼 CASE WHEN, 一条 UPDATE 全量重算(比逐行快且幂等)
_PRODUCT_SQL = f"""
UPDATE source_product SET quality_grade = CASE
  WHEN data_source=1 AND trust_years>={PRODUCT_GRADE_A['trust']}
       AND repurchase_rate>={PRODUCT_GRADE_A['repurchase']} AND sales_count>={PRODUCT_GRADE_A['sales']} THEN 'A'
  WHEN data_source=1 AND trust_years>={PRODUCT_GRADE_B['trust']}
       AND repurchase_rate>={PRODUCT_GRADE_B['repurchase']} AND sales_count>={PRODUCT_GRADE_B['sales']} THEN 'B'
  WHEN data_source=1 AND trust_years>={PRODUCT_GRADE_C['trust']}
       AND repurchase_rate>={PRODUCT_GRADE_C['repurchase']} AND sales_count>={PRODUCT_GRADE_C['sales']} THEN 'C'
  ELSE NULL
END"""

_FACTORY_SQL = f"""
UPDATE source_factory SET quality_grade = CASE
  WHEN platform_type=1 AND trust_years>={FACTORY_GRADE_A['trust']}
       AND avg_repurchase_rate>={FACTORY_GRADE_A['repurchase']}
       AND total_sales>={FACTORY_GRADE_A['total_sales']}
       AND product_count>={FACTORY_GRADE_A['product_count']} THEN 'A'
  WHEN platform_type=1 AND trust_years>={FACTORY_GRADE_B['trust']}
       AND avg_repurchase_rate>={FACTORY_GRADE_B['repurchase']}
       AND total_sales>={FACTORY_GRADE_B['total_sales']} THEN 'B'
  ELSE NULL
END"""


def _counts(cur, table, grade_col="quality_grade"):
    cur.execute(f"SELECT IFNULL({grade_col},'NULL') g, COUNT(*) n FROM {table} GROUP BY {grade_col} ORDER BY g")
    return cur.fetchall()


def _split(rows):
    """_counts 结果 -> (总行数, 有等级行数)。"""
    total = sum(n for _g, n in rows)
    graded = sum(n for g, n in rows if g != "NULL")
    return total, graded


def main():
    batch_id = begin_batch(DATASET, channel="derived")
    conn = cur = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("== 分级前 ==")
        before_p, before_f = _counts(cur, "source_product"), _counts(cur, "source_factory")
        print("source_product:", before_p)
        print("source_factory:", before_f)

        cur.execute(_PRODUCT_SQL)
        cur.execute(_FACTORY_SQL)
        conn.commit()

        print("\n== 分级后 ==")
        after_p, after_f = _counts(cur, "source_product"), _counts(cur, "source_factory")
        print("source_product:", after_p)
        print("source_factory:", after_f)

        # 幂等重算的"改动行数"永远接近 0，报它等于报"什么都没干"；台账记覆盖行数与出等级行数
        total = _split(before_p)[0] + _split(before_f)[0]
        graded = _split(after_p)[1] + _split(after_f)[1]
        end_batch(batch_id, "success", rows_total=total, rows_ok=graded)
        print("\n🎉 分级完成")
    except Exception as exc:
        end_batch(batch_id, "failed", error=f"{type(exc).__name__}: {exc}")
        # 跑挂和"守卫主动跳过"要分开报：前者是要修的 bug，后者可能只是机器没开
        cron_alert.write_alert(
            ALERT_KEY,
            f"货源质量分级未重算: {type(exc).__name__}: {str(exc)[:180]}",
            alert_type=cron_alert.FAILED_TYPE)
        raise
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
