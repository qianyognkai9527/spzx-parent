"""为抖店商品生成 AI 优化方案包 (task4)。

读取 douyin_products.jsonl, 为每个商品生成 outputs/douyin/{dyId}/optimization_plan.md:
- 标题清洗(去1688品牌/货号/痕迹词, 控抖音字数)
- 导购短标题(≤12汉字)
- 定价 = 货源价 × 2.5
- SKU颜色清理(去货号前缀)
- 属性推断(季节/材质/性别/风格/领型/裙型)
- 主图+详情图 AI生图 prompt (配合 ecommerce-main-image-skill)

方案包供 edit_douyin_product.py 执行 + 你人工审查。不自动上架。
用法:
  python gen_optimization_package.py              # 全量
  python gen_optimization_package.py --dyId 123   # 单个
  python gen_optimization_package.py --limit 5    # 前5个
"""
import csv
import json
import os
import sys

sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto")
from rules import BRAND_REMOVE, TRACE_WORDS, infer_attributes  # noqa: E402

import re

RAW_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_products.jsonl"
OUT_DIR = "/Users/qyk9527/outputs/douyin"
REVIEW_CSV = "/Users/qyk9527/outputs/douyin/review_queue.csv"
PRICE_MULT = 2.5
DOUYIN_TITLE_MAX = 60  # 抖音标题字数上限(宽松)


def clean_title(title):
    """去1688品牌/货号/痕迹词/ID, 控抖音字数。比 rules.rewrite_title 更宽松(不卡30)。"""
    if not title:
        return ""
    t = title.strip()
    for b in BRAND_REMOVE:
        t = t.replace(b, "")
    t = re.sub(r"[A-Za-z]{1,3}\d{3,5}", "", t)          # 货号
    t = re.sub(r"ID[：:]\s*\d+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\d{4,}", "", t)                          # 4位以上纯数字
    for kw in TRACE_WORDS:
        t = t.replace(kw, "")
    # 去常见厂家后缀
    for kw in ["制衣厂", "厂家", "工厂", "服饰", "源头"]:
        t = t.replace(kw, "")
    t = re.sub(r"\s+", "", t).strip()
    if len(t) > DOUYIN_TITLE_MAX:
        t = t[:DOUYIN_TITLE_MAX]
    return t


def guide_short_title(cleaned):
    """导购短标题: ≤12汉字/24字符(抖音按×2计数, 12汉字=24)。取清洗后标题前12个字符。"""
    return cleaned[:12] if cleaned else ""


def pricing(src_price):
    """货源价 × 2.5, 保留2位小数。"""
    try:
        return round(float(src_price) * PRICE_MULT, 2)
    except (TypeError, ValueError):
        return None


def sku_cleanup_plan(huohao, src_title):
    """SKU颜色清理: 去掉货号前缀(如 XMZ88;米红色 -> 米红色), 去重。"""
    plan = []
    if huohao:
        plan.append(f"- 去掉SKU颜色里的货号前缀 `{huohao};` (如 `{huohao};米红色` -> `米红色`)")
    plan.append("- 同色重复值合并, 防'规格值不能重复'")
    plan.append("- 去掉SKU里残留的1688货号/ID")
    return "\n".join(plan)


def image_prompts(cleaned, attrs):
    """主图+详情图 AI生图 prompt 模板 (配合 ecommerce-main-image-skill)。"""
    style = attrs.get("style", "简约")
    material = attrs.get("material", "")
    scene = "家居场景, 柔光, 干净背景" if "家居" in cleaned or "睡" in cleaned else "纯色背景, 棚拍"
    main_prompt = (
        f"产品: {cleaned}。{material}材质, {style}风格。{scene}, 高清电商主图, "
        f"无水印无文字无1688价格, 竖版3:4, 突出质感与卖点。"
    )
    detail_prompt = (
        f"详情图: {cleaned}。展示面料细节/版型/穿着效果, {scene}, 无厂家信息无水印, 横版或方版。"
    )
    return main_prompt, detail_prompt


def gen_one(p):
    dy_id = p.get("dyId") or ""
    if not dy_id:
        return None
    dy_title = p.get("dyTitle") or ""
    src_price = p.get("srcPrice")
    huohao = p.get("huohao") or ""
    supplier = p.get("supplier") or ""
    src_title = p.get("srcTitle") or ""

    cleaned = clean_title(dy_title)
    short = guide_short_title(cleaned)
    price = pricing(src_price)
    attrs = infer_attributes(cleaned)
    main_prompt, detail_prompt = image_prompts(cleaned, attrs)
    sku_plan = sku_cleanup_plan(huohao, src_title)

    md = f"""# 抖店商品优化方案 - {dy_id}

> ⚠️ 本方案为草稿, 供店主审查确认后再执行。不自动上架。

## 1. 标题优化
- 原抖音标题: {dy_title}
- 清洗后标题(去品牌/货号/1688痕迹): **{cleaned}**

## 2. 导购短标题 (≤12汉字/24字符)
- **{short}**

## 3. 定价 (货源价 × {PRICE_MULT})
- 货源价: ￥{src_price}
- 建议定价: **￥{price}**  (待店主确认)

## 4. SKU 颜色清理
{sku_plan}

## 5. 属性推断 (从标题, 需在编辑页核对)
{json.dumps(attrs, ensure_ascii=False, indent=2)}

## 6. 运费模板
- 选择"运费3.7"

## 7. 主图/详情图 AI生图 prompt (配合 ecommerce-main-image-skill, 人工生图+上传)
**主图 prompt:**
{main_prompt}

**详情图 prompt:**
{detail_prompt}

## 8. 执行清单
- [ ] 应用清洗后标题
- [ ] 填导购短标题
- [ ] 改定价 ￥{price}
- [ ] 清理SKU颜色
- [ ] 核对/补全属性
- [ ] 运费模板=运费3.7
- [ ] 主图/详情图: AI生图后手动上传
- [ ] 保存草稿(保持下架) - 不上架, 待审查

---
供应商(原始): {supplier} | 1688货号: {huohao} | 货源标题: {src_title}
"""
    return {
        "dyId": dy_id,
        "title_orig": dy_title,
        "title_cleaned": cleaned,
        "pricing": price,
        "supplier": supplier,
        "md": md,
    }


def main():
    dy_id_filter = None
    limit = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--dyId":
            dy_id_filter = sys.argv[i + 2]
        elif a == "--limit":
            limit = int(sys.argv[i + 2])

    if not os.path.exists(RAW_FILE):
        print(f"找不到 {RAW_FILE}, 先跑 crawl_douyin_isv.py")
        return
    items = []
    with open(RAW_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    if dy_id_filter:
        items = [p for p in items if p.get("dyId") == dy_id_filter]
    if limit:
        items = items[:limit]

    os.makedirs(OUT_DIR, exist_ok=True)
    review_rows = []
    for p in items:
        r = gen_one(p)
        if not r:
            continue
        d = os.path.join(OUT_DIR, r["dyId"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "optimization_plan.md"), "w", encoding="utf-8") as f:
            f.write(r["md"])
        review_rows.append(r)

    # review 队列
    with open(REVIEW_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dyId", "原标题", "清洗后标题", "建议定价", "供应商"])
        for r in review_rows:
            w.writerow([r["dyId"], r["title_orig"], r["title_cleaned"], r["pricing"], r["supplier"]])

    print(f"生成 {len(review_rows)} 个方案包 -> {OUT_DIR}/{{dyId}}/optimization_plan.md")
    print(f"审查队列 -> {REVIEW_CSV}")


if __name__ == "__main__":
    main()
