"""探查必填类目属性及其下拉选项"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')

        # 使用当前打开的编辑页面
        edit_page = None
        for page in browser.contexts[0].pages:
            if 'item.upload.taobao.com' in page.url:
                edit_page = page
                break
        if not edit_page:
            print("未找到编辑页面")
            return

        # 找出类目属性中所有带*的必填项和空值项
        result = await edit_page.evaluate("""
            () => {
                // 找到类目属性区域
                const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                if (!section) return {found: false, msg: 'no catProp section'};
                
                // 查找所有属性行 - 更精确的定位
                // 属性行通常是 label + select/input 的组合
                const rows = [];
                
                // 方法1: 找所有带 * 的标签
                const allEls = section.querySelectorAll('*');
                const labelsWithStar = [];
                for (const el of allEls) {
                    if (el.children.length === 0) {
                        const text = el.textContent.trim();
                        // 属性标签通常后面有 * 或 : 
                        if (text.includes('*') && text.length < 15) {
                            labelsWithStar.push(el);
                        }
                    }
                }
                
                // 对每个带*的标签，找它对应的控件
                for (const labelEl of labelsWithStar) {
                    // 向上找到包含这个label和控件的容器
                    let container = labelEl;
                    for (let i = 0; i < 5; i++) {
                        container = container.parentElement;
                        if (!container) break;
                        const select = container.querySelector('.next-select');
                        const input = container.querySelector('input[type="text"], input:not([type])');
                        if (select || input) {
                            const selectText = select ? select.textContent.trim() : '';
                            const inputValue = input ? input.value : '';
                            rows.push({
                                label: labelEl.textContent.trim().replace('*', ''),
                                select_text: selectText.substring(0, 40),
                                input_value: inputValue.substring(0, 20),
                                input_ph: input ? input.placeholder : '',
                                isEmpty: !selectText && !inputValue && !(select && selectText.includes('请选择'))
                            });
                            break;
                        }
                    }
                }
                
                // 去重
                const seen = new Set();
                const unique = [];
                for (const r of rows) {
                    const key = r.label + '|' + r.select_text + '|' + r.input_value;
                    if (!seen.has(key)) {
                        seen.add(key);
                        unique.push(r);
                    }
                }
                
                return {found: true, rows: unique};
            }
        """)

        print("=== 带*的类目属性 ===")
        for r in result.get('rows', []):
            empty = 'EMPTY' if r['isEmpty'] else 'filled'
            print(f"  {r['label']}: select='{r['select_text']}' input='{r['input_value']}' [{empty}]")

        # 对空的必填下拉，点击并获取选项
        print("\n=== 空必填下拉的选项 ===")
        for r in result.get('rows', []):
            if not r['isEmpty']:
                continue
            label = r['label']
            # 点击这个属性行的下拉
            clicked = await edit_page.evaluate("""
                (label) => {
                    const section = document.querySelector('#struct-catProp') || document.querySelector('#sell-field-catProp');
                    const allEls = section.querySelectorAll('*');
                    for (const el of allEls) {
                        if (el.children.length === 0 && el.textContent.trim().replace('*','') === label) {
                            let container = el;
                            for (let i = 0; i < 5; i++) {
                                container = container.parentElement;
                                if (!container) break;
                                const select = container.querySelector('.next-select');
                                if (select) {
                                    // 点击select的trigger
                                    const trigger = select.querySelector('.next-select-trigger') || select;
                                    trigger.click();
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                }
            """, label)
            if not clicked:
                print(f"  {label}: 无法点击下拉")
                continue
            await asyncio.sleep(1.5)

            opts = await edit_page.evaluate("""
                () => {
                    // 抓取下拉菜单选项
                    const items = document.querySelectorAll('.next-overlay-inner [class*="menu-item"], .next-select-menu-item, [class*="select-menu"] [class*="item"], [class*="menu"] [class*="item"]');
                    const seen = new Set();
                    const result = [];
                    for (const m of items) {
                        if (m.offsetParent !== null) {
                            const text = m.textContent.trim();
                            if (text && !seen.has(text)) {
                                seen.add(text);
                                result.push(text.substring(0, 40));
                            }
                        }
                    }
                    return result;
                }
            """)
            print(f"  {label} 选项: {opts}")
            if not opts:
                # 可能下拉在别的位置，抓取所有可见文本
                visible_text = await edit_page.evaluate("""
                    () => {
                        const menus = document.querySelectorAll('.next-overlay-inner, [class*="overlay"]');
                        const texts = [];
                        for (const m of menus) {
                            if (m.offsetParent !== null) {
                                texts.push(m.textContent.trim().substring(0, 100));
                            }
                        }
                        return texts;
                    }
                """)
                print(f"    可见overlay: {visible_text}")

            await edit_page.mouse.click(10, 10)
            await asyncio.sleep(0.8)

asyncio.run(main())
