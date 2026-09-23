"""彻底探查类目属性: 遍历所有空必填属性，抓取每个下拉的选项"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 找到已打开的编辑页面
        edit_page = None
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                edit_page = page
                break
        if not edit_page:
            print("未找到编辑页面")
            return

        print(f"编辑页面: {edit_page.url[:80]}")

        # 获取catProp下所有属性行 - 更广泛的选择器
        attrs = await edit_page.evaluate("""
            () => {
                const el = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                if (!el) return {found: false};
                
                // 尝试多种属性行的类名
                const rows = el.querySelectorAll(
                    '.sell-catProp-item, .catProp-item, .next-form-item, ' +
                    '.sell-component-info-wrapper-wrap, [class*="catProp"] [class*="item"], ' +
                    'dt, .prop-item, [class*="prop"] > div'
                );
                const seen = new Set();
                const result = [];
                for (const row of rows) {
                    if (seen.has(row)) continue;
                    seen.add(row);
                    
                    // 标签
                    const labelEl = row.querySelector('dt, .next-form-item-label, [class*="label"]:not([class*="component"]), em, .sell-form-label');
                    const labelText = labelEl ? labelEl.textContent.trim() : row.textContent.trim().split(/[：:]/)[0];
                    if (!labelText || labelText.length > 30) continue;
                    
                    const select = row.querySelector('.next-select');
                    const input = row.querySelector('input[type="text"], input:not([type]):not([class*="hidden"])');
                    
                    const selectText = select ? select.textContent.trim() : '';
                    const inputValue = input ? input.value : '';
                    
                    result.push({
                        label: labelText,
                        select: selectText.substring(0, 30),
                        input: inputValue.substring(0, 20),
                        input_ph: input ? (input.placeholder || '') : '',
                        itemlabel: input ? input.getAttribute('itemlabel') : ''
                    });
                }
                return {found: true, count: result.length, rows: result};
            }
        """)

        print("=== 类目属性所有行 ===")
        for r in attrs.get('rows', []):
            print(f"  label={r['label'][:20]} | select='{r['select']}' | input='{r['input']}' | ph='{r['input_ph']}' | itemlabel={r['itemlabel']}")

        # 点击每个空的下拉，抓取选项
        print("\n=== 抓取每个空必填下拉的选项 ===")
        options_map = {}
        for r in attrs.get('rows', []):
            label = r['label']
            # 跳过已有值或输入框字段
            if r['select'] and r['select'] not in ('请选择', ''):
                continue
            if r['input'] and not r['input_ph']:
                continue

            # 点击这个下拉
            clicked = await edit_page.evaluate("""
                (label) => {
                    const el = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    const rows = el.querySelectorAll('.sell-catProp-item, .catProp-item, .next-form-item, [class*="catProp"] [class*="item"], dt');
                    for (const row of rows) {
                        const labelEl = row.querySelector('dt, .next-form-item-label, [class*="label"]:not([class*="component"]), em');
                        const text = labelEl ? labelEl.textContent.trim() : '';
                        const select = row.querySelector('.next-select');
                        if (select && text === label) {
                            select.click();
                            return true;
                        }
                    }
                    return false;
                }
            """, label)
            if not clicked:
                continue
            await asyncio.sleep(1.5)

            opts = await edit_page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.next-overlay-inner .next-menu-item, .next-select-menu-item, [class*="menu-item"]');
                    const result = [];
                    for (const m of items) {
                        if (m.offsetParent !== null) {
                            result.push(m.textContent.trim().substring(0, 40));
                        }
                    }
                    return result;
                }
            """)
            if opts:
                options_map[label] = opts
                print(f"  {label}: {opts[:10]}")
            else:
                print(f"  {label}: (无选项或未打开)")

            # 关闭下拉
            await edit_page.mouse.click(10, 10)
            await asyncio.sleep(0.8)

        # 保存到文件
        with open('/Users/qyk9527/tb-auto/catprop_options.json', 'w', encoding='utf-8') as f:
            json.dump({'attrs': attrs.get('rows', []), 'options': options_map}, f, ensure_ascii=False, indent=2)
        print("\n结果已保存到 catprop_options.json")

asyncio.run(main())
