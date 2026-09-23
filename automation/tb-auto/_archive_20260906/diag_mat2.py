"""打开编辑页并检查材质百分比输入框"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break
        frame = isv_page.frames[2]
        await frame.evaluate("""
            (key) => {
                const row = document.querySelector(`tr[data-row-key="${key}"]`);
                const btn = Array.from(row.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'));
                btn.click();
            }
        """, "945571190")
        await asyncio.sleep(2)
        await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
        await asyncio.sleep(5)

        edit_page = None
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                edit_page = page
                break
        if not edit_page:
            print("未找到编辑页面")
            return
        await edit_page.wait_for_load_state('networkidle', timeout=30000)
        await asyncio.sleep(2)

        # 检查里料材质成分的material-item完整结构
        for label_text in ['里料材质成分', '面料材质成分']:
            info = await edit_page.evaluate("""
                (labelText) => {
                    const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    const items = section.querySelectorAll('div.sell-catProp-item');
                    for (const item of items) {
                        const label = item.querySelector('label.label');
                        if (label && label.textContent.includes(labelText)) {
                            const rows = item.querySelectorAll('.material-item');
                            const rowsInfo = [];
                            for (const r of rows) {
                                rowsInfo.push({
                                    text: r.textContent.trim().substring(0, 50),
                                    html: r.outerHTML.substring(0, 800)
                                });
                            }
                            return {id: item.id, rows: rowsInfo};
                        }
                    }
                    return null;
                }
            """, label_text)
            print(f"\n=== {label_text} ===")
            if info:
                for i, r in enumerate(info['rows']):
                    print(f"\n-- 行{i}: text={r['text']}")
                    print(f"   html={r['html'][:400]}")
            else:
                print("  未找到")

        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/diag_mat2.png', full_page=False)

asyncio.run(main())
