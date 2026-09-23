"""诊断: 检查产地等属性的DOM结构和下拉行为"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 打开编辑页面 (945571190)
        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break
        frame = isv_page.frames[2]

        # 找945571190
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

        # 列出所有类目属性行
        result = await edit_page.evaluate("""
            () => {
                const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                if (!section) return {found: false};
                const items = section.querySelectorAll('div.sell-catProp-item');
                const rows = [];
                for (const item of items) {
                    const label = item.querySelector('label.label');
                    const select = item.querySelector('.next-select');
                    const input = item.querySelector('input[type="text"], input:not([type])');
                    const radio = item.querySelector('input[type="radio"], .next-radio');
                    const textarea = item.querySelector('textarea');
                    rows.push({
                        id: item.id,
                        label: label ? label.textContent.trim() : '(无label)',
                        select_text: select ? select.textContent.trim().substring(0, 20) : '',
                        input_ph: input ? input.placeholder : '',
                        input_val: input ? input.value.substring(0, 15) : '',
                        has_radio: !!radio,
                        has_textarea: !!textarea
                    });
                }
                return {found: true, count: rows.length, rows: rows};
            }
        """)
        print("=== 所有类目属性行 ===")
        for r in result.get('rows', []):
            print(f"  id={r['id']} label={r['label'][:15]} | select='{r['select_text']}' | input_ph='{r['input_ph']}' | input='{r['input_val']}' | radio={r['has_radio']} textarea={r['has_textarea']}")

        # 点击产地，检查下拉行为
        print("\n=== 点击产地 ====")
        await edit_page.evaluate("""
            () => {
                const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                const items = section.querySelectorAll('div.sell-catProp-item');
                for (const item of items) {
                    const label = item.querySelector('label.label');
                    if (label && label.textContent.includes('产地')) {
                        const select = item.querySelector('.next-select');
                        if (select) select.click();
                        break;
                    }
                }
            }
        """)
        await asyncio.sleep(2)

        # 检查页面所有可见弹层
        overlays = await edit_page.evaluate("""
            () => {
                const results = [];
                const all = document.querySelectorAll('div, ul');
                for (const el of all) {
                    if (el.offsetParent !== null && el.textContent.trim()) {
                        const cls = el.className.toString();
                        // 只关注菜单/下拉/弹层相关
                        if (/menu|select|dropdown|overlay|popup|option/i.test(cls)) {
                            const t = el.textContent.trim();
                            if (t.length < 200) {
                                results.push({
                                    class: cls.substring(0, 70),
                                    text: t.substring(0, 80),
                                    tag: el.tagName,
                                    children: el.children.length
                                });
                            }
                        }
                    }
                }
                return results;
            }
        """)
        print("=== 点击后可见的菜单/下拉元素 ===")
        for o in overlays[:20]:
            print(f"  tag={o['tag']} class={o['class'][:40]} children={o['children']} text={o['text'][:40]}")

        # 检查是否有关联的overlay body元素
        body_overlays = await edit_page.evaluate("""
            () => {
                const results = [];
                const all = document.body.querySelectorAll('div');
                for (const el of all) {
                    const cls = el.className.toString();
                    if (/select-menu|menu-item|option/.test(cls)) {
                        results.push({class: cls.substring(0, 70), text: el.textContent.trim().substring(0, 50), parent: el.parentElement?.className?.toString().substring(0, 40)});
                    }
                }
                return results;
            }
        """)
        print("\n=== body中的select-menu元素 ===")
        for o in body_overlays[:20]:
            print(f"  class={o['class'][:40]} parent={o['parent']} text={o['text'][:40]}")

        await edit_page.screenshot(path='/Users/qyk9527/tb-auto/diagnose_catprop.png', full_page=False)
        print("\n截图已保存")

asyncio.run(main())
