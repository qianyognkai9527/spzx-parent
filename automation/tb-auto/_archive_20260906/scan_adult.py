"""扫描所有页，统计剩余情趣内衣商品"""
import asyncio
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

ADULT_KEYWORDS = ['情趣', '圣诞装', '制服', '角色扮演', '兔女郎', '丁字裤', '开裆', '免脱', '三点', '女仆', '连体衣', '绳衣']

def is_adult(title):
    return any(k in title for k in ADULT_KEYWORDS)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                for f in page.frames:
                    if 'isv-container' in (f.url or ''):
                        # 回到第1页
                        await f.evaluate("""
                            () => {
                                const first = document.querySelector('.ant-pagination-item-1, .ant-pagination-item:first-child');
                                if (first) first.click();
                            }
                        """)
                        await asyncio.sleep(3)
                        
                        total_adult = 0
                        scanned = 0
                        page_num = 0
                        adult_examples = []
                        
                        while page_num < 50:
                            rows = await f.evaluate("""
                                () => {
                                    const tbody = document.querySelector('.ant-table-tbody');
                                    if (!tbody) return [];
                                    const trs = tbody.querySelectorAll('tr.ant-table-row');
                                    return Array.from(trs).map(tr => tr.textContent.trim().substring(0, 80));
                                }
                            """)
                            if not rows:
                                logger.info(f"第{page_num+1}页无商品，结束扫描")
                                break
                            scanned += len(rows)
                            adult = [r for r in rows if is_adult(r)]
                            if adult:
                                total_adult += len(adult)
                                adult_examples.extend(adult[:2])
                                logger.info(f"第{page_num+1}页: {len(rows)}个, 情趣内衣{len(adult)}个")
                                for a in adult[:3]:
                                    logger.info(f"    {a[:40]}")
                            
                            # 下一页
                            next_btn = f.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                            if await next_btn.count() > 0:
                                await next_btn.first.click()
                                page_num += 1
                                await asyncio.sleep(3)
                            else:
                                logger.info(f"最后一页")
                                break
                        
                        logger.info(f"\n{'='*50}")
                        logger.info(f"扫描完成: 共扫描{scanned}个商品, 剩余情趣内衣{total_adult}个")
                        logger.info(f"{'='*50}")
                        break
                break
        browser.close()

asyncio.run(main())
