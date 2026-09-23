"""诊断: 检查row_key格式和编辑页提交按钮"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                frame = page.frames[2]

                # 检查所有行及其data-row-key
                rows_info = await frame.evaluate("""
                    () => {
                        const tbody = document.querySelector('.ant-table-tbody');
                        if (!tbody) return 'no tbody';
                        const trs = tbody.querySelectorAll('tr');
                        const result = [];
                        for (const tr of trs) {
                            const attrs = {};
                            for (const attr of tr.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            const hasEdit = !!Array.from(tr.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'));
                            result.push({
                                attrs: attrs,
                                has_edit_btn: hasEdit,
                                text: tr.textContent.trim().substring(0, 40)
                            });
                        }
                        return result;
                    }
                """)
                print("=== 表格行及属性 ===")
                for r in rows_info:
                    print(f"  attrs={json.dumps(r['attrs'], ensure_ascii=False)} | edit={r['has_edit_btn']} | text={r['text'][:30]}")
                break

        # 检查是否有编辑页面打开
        edit_pages = [pg for pg in browser.contexts[0].pages if 'item.upload.taobao.com' in pg.url]
        if edit_pages:
            print("\n=== 有编辑页面打开，检查提交按钮 ===")
            ep = edit_pages[0]
            btns = await ep.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, a');
                    return Array.from(btns).map(b => ({
                        text: b.textContent.trim().substring(0, 20),
                        tag: b.tagName,
                        class: b.className.substring(0, 60)
                    })).filter(b => b.text.length > 0 && (b.text.includes('提交') || b.text.includes('保存') || b.text.includes('草稿')));
                }
            """)
            for b in btns:
                print(f"  '{b['text']}' | tag={b['tag']} | class={b['class']}")
        else:
            print("\n=== 没有编辑页面打开 ===")

asyncio.run(main())
