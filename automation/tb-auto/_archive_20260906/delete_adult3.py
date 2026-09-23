"""按页码逐一删除情趣内衣 (稳健版)"""
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

async def get_total_pages(frame):
    text = await frame.evaluate("document.querySelector('.ant-pagination')?.textContent?.trim() || ''")
    import re
    m = re.search(r'共(\d+)条', text)
    total = int(m.group(1)) if m else 0
    return (total + 99) // 100 if total else 0

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
        page_num = 1

        while True:
            # 确保在第 page_num 页
            await frame.evaluate("""
                (n) => {
                    const items = document.querySelectorAll('.ant-pagination-item');
                    for (const it of items) {
                        if (it.textContent.trim() === String(n)) { it.click(); return true; }
                    }
                    // 尝试输入跳页
                    const jumper = document.querySelector('.ant-pagination-options-quick-jumper input');
                    if (jumper) {
                        jumper.value = String(n);
                        jumper.dispatchEvent(new Event('input', {bubbles: true}));
                        jumper.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', bubbles: true}));
                    }
                    return false;
                }
            """, page_num)
            await asyncio.sleep(4)

            # 确认当前页码
            cur = await frame.evaluate("document.querySelector('.ant-pagination-item-active')?.textContent?.trim() || ''")
            if cur and cur != str(page_num):
                logger.warning(f"跳到第{page_num}页失败，当前在{cur}页，尝试下一页按钮")
                next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    await asyncio.sleep(4)
                    page_num += 1
                    continue
                else:
                    break

            rows = await get_rows(frame)
            if not rows:
                logger.info(f"第{page_num}页无商品")
                break

            adult_rows = [r for r in rows if is_adult(r['title'])]
            if adult_rows:
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
                logger.info(f"第{page_num}页: 勾选{len(adult_rows)}个情趣内衣")

                del_btn = frame.locator('button:has-text("批量删除日志")')
                if await del_btn.count() > 0:
                    await del_btn.first.click()
                    await asyncio.sleep(2)
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
                        logger.info(f"  ✓ 删除{len(adult_rows)}个 (累计{total_deleted})")
                    else:
                        logger.error("  未找到确认按钮")
                await asyncio.sleep(6)
                # 删除后继续检查本页 (页码不变)
                continue

            # 本页无情趣内衣，去下一页
            logger.info(f"第{page_num}页无情趣内衣，翻页")
            next_btn = frame.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
            if await next_btn.count() > 0:
                await next_btn.first.click()
                page_num += 1
                await asyncio.sleep(4)
            else:
                break

        logger.info(f"\n{'='*50}")
        logger.info(f"删除完成！共删除 {total_deleted} 个")
        logger.info(f"{'='*50}")
        browser.close()

asyncio.run(main())
