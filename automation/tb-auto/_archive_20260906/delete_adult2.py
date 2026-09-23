"""删除所有页的情趣内衣商品 (修复版)"""
import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ADULT_KEYWORDS = ['情趣', '圣诞装', '制服', '角色扮演', '兔女郎', '丁字裤', '开裆', '免脱', '三点', '女仆', '连体衣', '绳衣']

def is_adult(title):
    return any(k in title for k in ADULT_KEYWORDS)

async def get_rows(frame):
    return await frame.evaluate("""
        () => {
            const tbody = document.querySelector('.ant-table-tbody');
            if (!tbody) return [];
            const trs = tbody.querySelectorAll('tr.ant-table-row');
            return Array.from(trs).map((tr, idx) => ({
                title: tr.textContent.trim().substring(0, 80),
                index: idx
            }));
        }
    """)

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
        consecutive_empty_pages = 0
        page_iter = 0

        while page_iter < 300:
            # 获取当前页
            cur_page = await frame.evaluate("document.querySelector('.ant-pagination-item-active')?.textContent?.trim() || '1'")
            rows = await get_rows(frame)
            
            if not rows:
                consecutive_empty_pages += 1
                if consecutive_empty_pages > 3:
                    logger.info("连续多页无商品，结束")
                    break
                # 尝试下一页
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_iter += 1
                    await asyncio.sleep(4)
                    continue
                else:
                    logger.info("没有更多页面了")
                    break

            consecutive_empty_pages = 0
            adult_rows = [r for r in rows if is_adult(r['title'])]
            
            if not adult_rows:
                # 本页无情趣内衣，翻页
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    page_iter += 1
                    await asyncio.sleep(4)
                    continue
                else:
                    logger.info(f"第{cur_page}页无情趣内衣且无下一页，结束")
                    break

            # 勾选本页所有情趣内衣
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
            await asyncio.sleep(2)

            logger.info(f"第{cur_page}页: {len(rows)}个, 勾选{len(adult_rows)}个情趣内衣")

            # 点击批量删除
            del_btn = frame.locator('button:has-text("批量删除日志")')
            if await del_btn.count() > 0:
                await del_btn.first.click()
                await asyncio.sleep(2)
                # 确认
                confirmed = await frame.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('.ant-modal button');
                        for (const b of btns) {
                            if (b.textContent.includes('确 定') || b.textContent.includes('确定')) {
                                b.click(); return true;
                            }
                        }
                        return false;
                    }
                """)
                if confirmed:
                    total_deleted += len(adult_rows)
                    logger.info(f"  ✓ 删除 {len(adult_rows)} 个 (累计 {total_deleted})")
                else:
                    logger.error("  未找到确认按钮，取消")
                    await frame.evaluate("""
                        () => {
                            const btns = document.querySelectorAll('.ant-modal button');
                            for (const b of btns) {
                                if (b.textContent.includes('取 消')) { b.click(); return; }
                            }
                        }
                    """)
            else:
                logger.error("  未找到批量删除按钮")
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

            # 等待列表刷新 (删除后页面可能回到第1页或本页)
            await asyncio.sleep(5)

            page_iter += 1
            if page_iter % 5 == 0:
                logger.info(f"进度: 已删除 {total_deleted} 个, 当前第{cur_page}页")

        logger.info(f"\n{'='*50}")
        logger.info(f"删除完成！共删除 {total_deleted} 个情趣内衣商品")
        logger.info(f"{'='*50}")
        browser.close()

asyncio.run(main())
