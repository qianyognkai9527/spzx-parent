"""识别情趣内衣商品并测试删除"""
import asyncio
import json
from playwright.async_api import async_playwright

# 情趣内衣关键词 (成人资质类目)
ADULT_KEYWORDS = ['情趣', '圣诞装', '角色扮演', '兔女郎', '丁字裤', '开裆', '免脱', '三点']

async def is_adult_product(title):
    for kw in ADULT_KEYWORDS:
        if kw in title:
            return True
    return False

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                for f in page.frames:
                    if 'isv-container' in (f.url or ''):
                        # 获取当前页所有行
                        rows = await f.evaluate("""
                            () => {
                                const tbody = document.querySelector('.ant-table-tbody');
                                const trs = tbody.querySelectorAll('tr.ant-table-row');
                                return Array.from(trs).map(tr => ({
                                    title: tr.textContent.trim().substring(0, 60),
                                    row_key: tr.getAttribute('data-row-key'),
                                    index: Array.from(tbody.children).indexOf(tr)
                                }));
                            }
                        """)
                        
                        # 识别情趣内衣
                        adult_rows = []
                        for r in rows:
                            if is_adult_product(r['title']):
                                adult_rows.append(r)
                        
                        print(f"当前页共 {len(rows)} 个商品")
                        print(f"其中情趣内衣 {len(adult_rows)} 个:")
                        for r in adult_rows:
                            print(f"  [{r['row_key']}] {r['title'][:40]}")
                        
                        # 如果有情趣内衣，测试删除第一个
                        if adult_rows:
                            first = adult_rows[0]
                            print(f"\n测试删除: {first['title'][:40]}")
                            
                            # 选中该行的复选框
                            await f.evaluate("""
                                (index) => {
                                    const tbody = document.querySelector('.ant-table-tbody');
                                    const trs = tbody.querySelectorAll('tr.ant-table-row');
                                    const tr = trs[index];
                                    const cb = tr.querySelector('input[type="checkbox"]');
                                    if (cb) cb.click();
                                }
                            """, first['index'])
                            await asyncio.sleep(1)
                            print("已勾选复选框")
                            
                            # 点击批量删除日志
                            del_btn = f.locator('button:has-text("批量删除日志")')
                            if await del_btn.count() > 0:
                                await del_btn.first.click()
                                print("已点击批量删除日志")
                                await asyncio.sleep(2)
                                
                                # 检查确认弹框
                                modal = await f.evaluate("""
                                    () => {
                                        const modals = document.querySelectorAll('.ant-modal, [class*="modal"], [class*="confirm"]');
                                        const results = [];
                                        for (const m of modals) {
                                            if (m.offsetParent !== null && m.textContent.trim()) {
                                                results.push({
                                                    class: m.className.substring(0, 40),
                                                    text: m.textContent.trim().substring(0, 200),
                                                    buttons: Array.from(m.querySelectorAll('button')).map(b => b.textContent.trim())
                                                });
                                            }
                                        }
                                        return results;
                                    }
                                """)
                                print("\n=== 确认弹框 ===")
                                print(json.dumps(modal, ensure_ascii=False, indent=2))
                        break
                break
        browser.close()

asyncio.run(main())
