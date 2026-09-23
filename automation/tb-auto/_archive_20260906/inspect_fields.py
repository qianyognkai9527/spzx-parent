"""
精准定位脚本 - 找到每个目标字段的具体DOM结构和选择器
"""
import asyncio
import json
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        page = context.pages[0]

        print(f"[*] 当前页面: {page.url[:80]}")

        # ===== 1. 找货号输入框 =====
        print("\n=== 1. 货号 ===")
        huohao_info = await page.evaluate("""
            () => {
                const labels = Array.from(document.querySelectorAll('*'));
                const results = [];
                for (const el of labels) {
                    if (el.children.length === 0 && el.textContent.trim() === '货号') {
                        // 找到标签，向上找 form-item，再找 input
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"]');
                        if (formItem) {
                            const input = formItem.querySelector('input[type="text"], input:not([type])');
                            if (input) {
                                results.push({
                                    label_text: el.textContent.trim(),
                                    input_value: input.value,
                                    input_class: input.className,
                                    form_item_class: formItem.className,
                                    html_snippet: formItem.outerHTML.substring(0, 300)
                                });
                            }
                        }
                    }
                }
                return results;
            }
        """)
        for info in huohao_info:
            print(f"  value={info['input_value']}, class={info['input_class'][:50]}")
            print(f"  form_item_class={info['form_item_class'][:60]}")

        # ===== 2. 找价格输入框 =====
        print("\n=== 2. 价格 (一口价) ===")
        price_info = await page.evaluate("""
            () => {
                const results = [];
                // 找所有包含"一口价"的文本节点
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent.includes('一口价')) {
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"], tr, .sku-item, [class*="price"]');
                        if (formItem) {
                            const inputs = formItem.querySelectorAll('input[type="text"], input:not([type])');
                            for (const input of inputs) {
                                if (input.value && /^\\d+\\.?\\d*$/.test(input.value)) {
                                    results.push({
                                        label: el.textContent.trim().substring(0, 30),
                                        value: input.value,
                                        class: input.className,
                                        parent_class: formItem.className,
                                        parent_tag: formItem.tagName
                                    });
                                }
                            }
                        }
                    }
                }
                // 也找所有带数字值的input（可能是SKU价格）
                const allInputs = document.querySelectorAll('input[type="text"], input:not([type])');
                for (const input of allInputs) {
                    if (input.value && /^\\d+\\.\\d{2}$/.test(input.value)) {
                        results.push({
                            label: '(by value pattern)',
                            value: input.value,
                            class: input.className,
                            parent_tag: input.parentElement?.tagName,
                            parent_class: input.parentElement?.className?.substring(0, 50)
                        });
                    }
                }
                return results;
            }
        """)
        for info in price_info:
            print(f"  label={info.get('label','')[:20]} | value={info['value']} | class={info.get('class','')[:40]} | parent={info.get('parent_tag','')} {info.get('parent_class','')[:40]}")

        # ===== 3. 找店铺中分类 =====
        print("\n=== 3. 店铺中分类 ===")
        shop_cat_info = await page.evaluate("""
            () => {
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent.trim() === '店铺中分类') {
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"]');
                        if (!formItem) formItem = el.parentElement?.parentElement;
                        if (formItem) {
                            const select = formItem.querySelector('.next-select, [class*="select"]');
                            return {
                                found: true,
                                label_text: el.textContent.trim(),
                                form_item_class: formItem.className?.substring(0, 60),
                                select_class: select?.className?.substring(0, 60),
                                select_text: select?.textContent?.trim().substring(0, 50),
                                html_snippet: formItem.outerHTML.substring(0, 500)
                            };
                        }
                    }
                }
                return {found: false};
            }
        """)
        print(f"  found={shop_cat_info.get('found')}")
        if shop_cat_info.get('found'):
            print(f"  select_text={shop_cat_info.get('select_text')}")
            print(f"  select_class={shop_cat_info.get('select_class')}")
            print(f"  html={shop_cat_info.get('html_snippet', '')[:200]}")

        # ===== 4. 找上架时间 ===
        print("\n=== 4. 上架时间 ===")
        listing_info = await page.evaluate("""
            () => {
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent.trim() === '上架时间') {
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"]');
                        if (!formItem) formItem = el.parentElement?.parentElement?.parentElement;
                        if (formItem) {
                            // 找所有可点击的选项
                            const options = formItem.querySelectorAll('label, [class*="radio"], input[type="radio"], span');
                            const optTexts = [];
                            for (const opt of options) {
                                const text = opt.textContent.trim();
                                if (text && text.length < 20 && ['立刻上架', '定时上架', '放入仓库'].some(k => text.includes(k))) {
                                    optTexts.push({
                                        text: text,
                                        tag: opt.tagName,
                                        class: opt.className?.substring(0, 50)
                                    });
                                }
                            }
                            return {
                                found: true,
                                form_item_class: formItem.className?.substring(0, 60),
                                options: optTexts,
                                html_snippet: formItem.outerHTML.substring(0, 500)
                            };
                        }
                    }
                }
                return {found: false};
            }
        """)
        print(f"  found={listing_info.get('found')}")
        if listing_info.get('found'):
            for opt in listing_info.get('options', []):
                print(f"  option: text={opt['text']} | tag={opt['tag']} | class={opt['class']}")
            print(f"  html={listing_info.get('html_snippet', '')[:300]}")

        # ===== 5. 找商品预检 =====
        print("\n=== 5. 商品预检 ===")
        precheck_info = await page.evaluate("""
            () => {
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent.trim() === '商品预检') {
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"]');
                        if (!formItem) formItem = el.parentElement?.parentElement?.parentElement;
                        if (formItem) {
                            const checkbox = formItem.querySelector('input[type="checkbox"], .next-checkbox, [class*="checkbox"]');
                            const toggle = formItem.querySelector('[class*="switch"], [class*="toggle"]');
                            const labels = formItem.querySelectorAll('label, span');
                            const labelTexts = [];
                            for (const l of labels) {
                                const t = l.textContent.trim();
                                if (t && t.length < 20) labelTexts.push({text: t, tag: l.tagName, class: l.className?.substring(0, 40)});
                            }
                            return {
                                found: true,
                                form_item_class: formItem.className?.substring(0, 60),
                                checkbox_class: checkbox?.className?.substring(0, 60),
                                checkbox_checked: checkbox?.checked || checkbox?.getAttribute('aria-checked'),
                                toggle_class: toggle?.className?.substring(0, 60),
                                labels: labelTexts,
                                html_snippet: formItem.outerHTML.substring(0, 500)
                            };
                        }
                    }
                }
                return {found: false};
            }
        """)
        print(f"  found={precheck_info.get('found')}")
        if precheck_info.get('found'):
            print(f"  checkbox_class={precheck_info.get('checkbox_class')}")
            print(f"  checkbox_checked={precheck_info.get('checkbox_checked')}")
            print(f"  labels={precheck_info.get('labels')}")
            print(f"  html={precheck_info.get('html_snippet', '')[:300]}")

        # ===== 6. 找宝贝标题 =====
        print("\n=== 6. 宝贝标题 ===")
        title_info = await page.evaluate("""
            () => {
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0 && el.textContent.includes('宝贝标题')) {
                        let formItem = el.closest('.next-form-item, .form-item, [class*="form-item"]');
                        if (!formItem) formItem = el.parentElement?.parentElement;
                        if (formItem) {
                            const input = formItem.querySelector('input[type="text"], input:not([type])');
                            return {
                                found: true,
                                value: input?.value,
                                class: input?.className?.substring(0, 50),
                                placeholder: input?.placeholder,
                                form_item_class: formItem.className?.substring(0, 60)
                            };
                        }
                    }
                }
                return {found: false};
            }
        """)
        print(f"  found={title_info.get('found')}")
        if title_info.get('found'):
            print(f"  value={title_info.get('value')}")
            print(f"  placeholder={title_info.get('placeholder')}")

        # ===== 7. 找提交按钮 =====
        print("\n=== 7. 提交按钮 ===")
        submit_info = await page.evaluate("""
            () => {
                const buttons = document.querySelectorAll('button, [role="button"], .next-btn, .ant-btn');
                const results = [];
                for (const btn of buttons) {
                    const text = btn.textContent.trim();
                    if (text && text.length < 20) {
                        results.push({
                            text: text,
                            class: btn.className?.substring(0, 60),
                            tag: btn.tagName
                        });
                    }
                }
                return results;
            }
        """)
        for btn in submit_info:
            print(f"  '{btn['text']}' | tag={btn['tag']} | class={btn['class'][:50]}")

        browser.close()


if __name__ == "__main__":
    asyncio.run(main())
