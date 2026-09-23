"""删除最近30天铺货失败的情趣内衣类商品"""
import asyncio
import json
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 情趣内衣关键词 (成人资质类目，必失败)
ADULT_KEYWORDS = ['情趣', '圣诞装', '制服', '角色扮演', '兔女郎', '丁字裤', '开裆', '免脱', '三点', '女仆', '连体衣', '绳衣']


def is_adult_product(title):
    for kw in ADULT_KEYWORDS:
        if kw in title:
            return True
    return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break

        frame = None
        for f in isv_page.frames:
            if 'isv-container' in (f.url or ''):
                frame = f
                break

        if not frame:
            logger.error("未找到ISV frame")
            return

        total_deleted = 0
        page_num = 0
        max_pages = 200  # 安全上限

        while page_num < max_pages:
            # 获取当前页所有行
            rows = await frame.evaluate("""
                () => {
                    const tbody = document.querySelector('.ant-table-tbody');
                    if (!tbody) return [];
                    const trs = tbody.querySelectorAll('tr.ant-table-row');
                    return Array.from(trs).map((tr, idx) => ({
                        title: tr.textContent.trim().substring(0, 80),
                        row_key: tr.getAttribute('data-row-key'),
                        index: idx
                    }));
                }
            """)

            if not rows:
                logger.info(f"第{page_num+1}页无商品，尝试翻页...")
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_num += 1
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.info("没有更多页面了")
                    break

            # 识别情趣内衣
            adult_rows = [r for r in rows if is_adult_product(r['title'])]
            logger.info(f"第{page_num+1}页: 共{len(rows)}个商品, 情趣内衣{len(adult_rows)}个")

            if not adult_rows:
                # 没有情趣内衣，翻页
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_num += 1
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.info("没有更多页面了")
                    break

            # 勾选情趣内衣的行
            for r in adult_rows:
                await frame.evaluate("""
                    (index) => {
                        const tbody = document.querySelector('.ant-table-tbody');
                        const trs = tbody.querySelectorAll('tr.ant-table-row');
                        const tr = trs[index];
                        if (tr) {
                            const cb = tr.querySelector('input[type="checkbox"]');
                            if (cb && !cb.checked) cb.click();
                        }
                    }
                """, r['index'])
            await asyncio.sleep(1.5)

            deleted_titles = [r['title'][:30] for r in adult_rows]
            logger.info(f"  勾选 {len(adult_rows)} 个: {deleted_titles}")

            # 点击批量删除日志
            del_btn = frame.locator('button:has-text("批量删除日志")')
            if await del_btn.count() == 0:
                logger.error("  未找到批量删除按钮，跳过本页")
                # 取消勾选
                await frame.evaluate("""
                    () => {
                        const tbody = document.querySelector('.ant-table-tbody');
                        const trs = tbody.querySelectorAll('tr.ant-table-row');
                        for (const tr of trs) {
                            const cb = tr.querySelector('input[type=checkbox]');
                            if (cb && cb.checked) cb.click();
                        }
                    }
                """)
                await asyncio.sleep(1)
                # 翻页
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_num += 1
                    await asyncio.sleep(3)
                else:
                    break
                continue

            await del_btn.first.click()
            await asyncio.sleep(2)

            # 确认删除
            confirmed = await frame.evaluate("""
                () => {
                    const btns = document.querySelectorAll('.ant-modal button');
                    for (const b of btns) {
                        if (b.textContent.includes('确 定') || b.textContent.includes('确定')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if confirmed:
                logger.info(f"  ✓ 已确认删除 {len(adult_rows)} 个")
                total_deleted += len(adult_rows)
            else:
                logger.error("  未找到确定按钮，取消操作")
                # 点取消
                await frame.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('.ant-modal button');
                        for (const b of btns) {
                            if (b.textContent.includes('取 消')) { b.click(); return; }
                        }
                    }
                """)

            # 等待列表刷新
            await asyncio.sleep(4)

            # 删除后本页商品减少，继续处理本页 (不翻页)
            # 但如果本页没有更多情趣内衣，翻页
            rows2 = await frame.evaluate("""
                () => {
                    const tbody = document.querySelector('.ant-table-tbody');
                    if (!tbody) return [];
                    const trs = tbody.querySelectorAll('tr.ant-table-row');
                    return Array.from(trs).map((tr, idx) => ({
                        title: tr.textContent.trim().substring(0, 80),
                        row_key: tr.getAttribute('data-row-key'),
                        index: idx
                    }));
                }
            """)
            adult2 = [r for r in rows2 if is_adult_product(r['title'])]
            if not adult2:
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_num += 1
                    await asyncio.sleep(3)
                else:
                    break

            logger.info(f"累计删除: {total_deleted} 个")

        logger.info(f"\n{'='*50}")
        logger.info(f"删除完成！共删除 {total_deleted} 个情趣内衣商品")
        logger.info(f"{'='*50}")

        browser.close()


if __name__ == "__main__":
    asyncio.run(main())
