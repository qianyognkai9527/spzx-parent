"""诊断: 材质成分区域的百分比输入结构"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 打开945571190的编辑页
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

        # 检查材质成分区域的结构
        struct = await edit_page.evaluate("""
            () => {
                const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                if (!section) return 'no section';
                // 找材质成分相关的行
                const items = section.querySelectorAll('div.sell-catProp-item');
                const result = [];
                for (const item of items) {
                    const label = item.querySelector('label.label');
                    const labelText = label ? label.textContent.trim() : '';
                    if (labelText.includes('材质成分') || labelText.includes('材质')) {
                        result.push({
                            id: item.id,
                            label: labelText,
                            html: item.outerHTML.substring(0, 2500)
                        });
                    }
                }
                return result;
            }
        """)
        for s in struct:
            print(f"\n=== {s['label']} (id={s['id']}) ===")
            print(s['html'])
            print()

        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/diagnose_material.png', full_page=False)

asyncio.run(main())
