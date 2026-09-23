"""检查上架时间和店铺中分类的精确DOM结构"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                # 上架时间完整HTML
                listing_html = await page.evaluate("""
                    () => {
                        const el = document.querySelector('#sell-field-startTime');
                        if (!el) return 'not found';
                        // 找到 radio 相关的所有元素
                        const radios = el.querySelectorAll('.sell-radio, .radio-item, label, input[type="radio"], .next-radio');
                        const items = [];
                        for (const r of radios) {
                            items.push({
                                tag: r.tagName,
                                class: r.className.toString().substring(0, 60),
                                text: r.textContent.trim().substring(0, 20),
                                html: r.outerHTML.substring(0, 200),
                                has_input: !!r.querySelector('input'),
                                input_type: r.querySelector('input')?.type,
                                input_checked: r.querySelector('input')?.checked,
                                input_name: r.querySelector('input')?.name
                            });
                        }
                        return items;
                    }
                """)
                print("=== 上架时间 radio 元素 ===")
                import json
                for item in listing_html:
                    print(json.dumps(item, ensure_ascii=False, indent=2))
                    print()

                # 店铺中分类 - 先打开下拉再检查
                print("\n=== 店铺中分类 ===")
                await page.locator('#sell-field-shopcat .next-select-trigger').click()
                await asyncio.sleep(2)

                tree_html = await page.evaluate("""
                    () => {
                        const nodes = document.querySelectorAll('.next-overlay-inner .next-tree-node');
                        const items = [];
                        for (const n of nodes) {
                            items.push({
                                tag: n.tagName,
                                class: n.className.toString().substring(0, 80),
                                text: n.textContent.trim().substring(0, 30),
                                html: n.outerHTML.substring(0, 300),
                                inner_html: n.querySelector('.next-tree-node-inner')?.outerHTML?.substring(0, 200) || ''
                            });
                        }
                        return items;
                    }
                """)
                for item in tree_html[:2]:
                    print(json.dumps(item, ensure_ascii=False, indent=2))
                    print()

                # 关闭下拉
                await page.mouse.click(10, 10)
                break

asyncio.run(main())
