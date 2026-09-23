"""探查类目属性(catProp)结构 - 找出所有必填属性和下拉选项"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 打开一个编辑页面
        isv_page = None
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                isv_page = page
                break
        frame = isv_page.frames[2]

        # 找到第一个未处理的商品
        rows = await frame.evaluate("""
            () => {
                const tbody = document.querySelector('.ant-table-tbody');
                const trs = tbody.querySelectorAll('tr.ant-table-row');
                return Array.from(trs).map(tr => ({
                    key: tr.getAttribute('data-row-key'),
                    has_edit: !!Array.from(tr.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'))
                })).filter(r => r.has_edit);
            }
        """)

        # 用第一个商品
        row_key = rows[0]['key']
        print(f"使用商品 row_key={row_key}")

        # 点击编辑店铺草稿 -> 继续上架
        await frame.evaluate("""
            (key) => {
                const row = document.querySelector(`tr[data-row-key="${key}"]`);
                const btn = Array.from(row.querySelectorAll('button')).find(b => b.textContent.includes('编辑店铺草稿'));
                btn.click();
            }
        """, row_key)
        await asyncio.sleep(2)
        await frame.locator('.ant-modal button:has-text("继续上架")').first.click()
        await asyncio.sleep(4)

        # 找到编辑页面
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

        # 分析类目属性结构
        catprop = await edit_page.evaluate("""
            () => {
                const el = document.querySelector('#sell-field-catProp, #struct-catProp');
                if (!el) return {found: false};
                
                // 找所有属性项 (label + control)
                const items = el.querySelectorAll('.sell-catProp-item, [class*="catProp-item"], [class*="prop-item"], .next-form-item');
                const result = [];
                for (const item of items) {
                    const label = item.querySelector('dt, .next-form-item-label, [class*="label"]');
                    const labelText = label ? label.textContent.trim().substring(0, 20) : '';
                    if (!labelText) continue;
                    
                    // 找下拉/输入
                    const select = item.querySelector('.next-select');
                    const input = item.querySelector('input[type="text"], input:not([type])');
                    const required = item.textContent.includes('*') || labelText.includes('*');
                    
                    result.push({
                        label: labelText,
                        required: required,
                        has_select: !!select,
                        select_text: select ? select.textContent.trim().substring(0, 30) : '',
                        has_input: !!input,
                        input_value: input ? input.value : '',
                        input_placeholder: input ? (input.placeholder || '') : '',
                        class: item.className.substring(0, 60)
                    });
                }
                
                return {found: true, count: result.length, items: result};
            }
        """)
        print("=== 类目属性项 ===")
        for item in catprop.get('items', []):
            status = '必填' if item['required'] else '选填'
            empty = 'EMPTY' if item['required'] and not item['select_text'] and not item['input_value'] else ''
            print(f"  [{status}] {item['label']} | select='{item['select_text']}' | input='{item['input_value']}' | ph='{item['input_placeholder']}' {empty}")

        # 找一个空的必填下拉，点击看看选项
        print("\n=== 点击一个空必填下拉看选项 ===")
        await edit_page.evaluate("""
            () => {
                const el = document.querySelector('#sell-field-catProp, #struct-catProp');
                const items = el.querySelectorAll('.sell-catProp-item, [class*="catProp-item"], .next-form-item');
                for (const item of items) {
                    const label = item.querySelector('dt, .next-form-item-label, [class*="label"]');
                    if (!label) continue;
                    const labelText = label.textContent.trim();
                    const select = item.querySelector('.next-select');
                    if (select && labelText.includes('产地')) {
                        select.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        await asyncio.sleep(2)
        options = await edit_page.evaluate("""
            () => {
                const menus = document.querySelectorAll('.next-overlay-inner .next-menu-item, .next-select-menu-item, [class*="select-menu"] [class*="item"]');
                const opts = [];
                for (const m of menus) {
                    if (m.offsetParent !== null) {
                        opts.push(m.textContent.trim().substring(0, 30));
                    }
                }
                return opts.slice(0, 30);
            }
        """)
        print(f"产地下拉选项: {options}")

        # 关闭下拉
        await edit_page.mouse.click(10, 10)
        await asyncio.sleep(1)

        # 检查材质成分结构
        print("\n=== 材质成分结构 ===")
        material_info = await edit_page.evaluate("""
            () => {
                const el = document.querySelector('#struct-catProp, #sell-field-catProp');
                const text = el ? el.textContent : '';
                const idx = text.indexOf('材质成分');
                return {found: idx > -1, snippet: text.substring(Math.max(0, idx-50), idx + 200)};
            }
        """)
        print(json.dumps(material_info, ensure_ascii=False, indent=2))

asyncio.run(main())
