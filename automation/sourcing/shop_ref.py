"""店铺归属：自动化脚本写库时统一从这里取 shop_id。

店铺身份只存在于 shop 表，脚本不硬编码店铺 ID；取不到时返回 None，
由调用方决定是留空（归属未知）还是跳过写入，绝不伪造一个店。
入参统一用游标，各脚本已有 cur，且不能在这里关掉调用方的游标。
"""

PLATFORM_TAOBAO = 1
PLATFORM_DOUYIN = 2
PLATFORM_PINDUODUO = 3


def default_shop_id(cur, platform_code):
    """该平台 is_default=1 且启用的店铺 id，没有则 None。"""
    if not platform_code:
        return None
    cur.execute(
        "SELECT id FROM shop WHERE platform_code=%s AND is_default=1 AND status=1 LIMIT 1",
        (platform_code,))
    row = cur.fetchone()
    return row[0] if row else None


def shop_id_of_product(cur, platform_product_id):
    """经由平台商品反查店铺；货源侧告警没有 platform_product_id，返回 None。"""
    if not platform_product_id:
        return None
    cur.execute("SELECT shop_id FROM platform_product WHERE id=%s", (platform_product_id,))
    row = cur.fetchone()
    return row[0] if row else None
