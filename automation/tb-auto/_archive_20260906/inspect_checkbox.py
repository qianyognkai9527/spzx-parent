"""检查复选框机制和筛选状态"""
import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        for page in browser.contexts[0].pages:
            if 'ufuwu.1688.com' in page.url:
                for f in page.frames:
                    if 'isv-container' in (f.url or ''):
                        # 检查筛选状态 (tabs和筛选器)
                        state = await f.evaluate("""
                            () => {
                                const result = {};
                                // tabs
                                const tabs = document.querySelectorAll('.ant-tabs-tab');
                                result.tabs = Array.from(tabs).map(t => ({
                                    text: t.textContent.trim().substring(0, 30),
                                    active: t.className.includes('active')
                                }));
                                // 筛选区域
                                const filterText = document.querySelector('.ant-pro-query-filter, [class*="query-filter"]');
                                result.filter = filterText ? filterText.textContent.trim().substring(0, 100) : 'none';
                                return result;
                            }
                        """)
                        print("=== 筛选状态 ===")
                        print(json.dumps(state, ensure_ascii=False, indent=2))

                        # 检查第一行数据的复选框结构
                        row_checkbox = await f.evaluate("""
                            () => {
                                const tbody = document.querySelector('.ant-table-tbody');
                                const tr = tbody.querySelector('tr.ant-table-row');
                                if (!tr) return 'no row';
                                // 找复选框
                                const cb = tr.querySelector('input[type="checkbox"], [class*="checkbox"], [class*="selection"]');
                                if (!cb) return 'no checkbox in row';
                                return {
                                    tag: cb.tagName,
                                    class: cb.className.substring(0, 50),
                                    html: cb.outerHTML.substring(0, 200)
                                };
                            }
                        """)
                        print("\n=== 行复选框 ===")
                        print(json.dumps(row_checkbox, ensure_ascii=False, indent=2))

                        # 点击第一个复选框，看选中效果
                        await f.evaluate("""
                            () => {
                                const tbody = document.querySelector('.ant-table-tbody');
                                const tr = tbody.querySelector('tr.ant-table-row');
                                const cb = tr.querySelector('input[type="checkbox"]');
                                if (cb) cb.click();
                            }
                        """)
                        await asyncio.sleep(1)
                        selected_state = await f.evaluate("""
                            () => {
                                const tbody = document.querySelector('.ant-table-tbody');
                                const tr = tbody.querySelector('tr.ant-table-row');
                                const cb = tr.querySelector('input[type="checkbox"]');
                                return {
                                    checked: cb ? cb.checked : null,
                                    row_class: tr.className
                                };
                            }
                        """)
                        print("\n=== 点击后 ===")
                        print(json.dumps(selected_state, ensure_ascii=False, indent=2))

                        # 检查批量操作按钮是否变化
                        batch_btns = await f.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('button')).filter(b => {
                                    const t = b.textContent.trim();
                                    return t.includes('批量');
                                }).map(b => ({
                                    text: b.textContent.trim(),
                                    class: b.className.substring(0, 40),
                                    disabled: b.disabled
                                }));
                            }
                        """)
                        print("\n=== 批量按钮 ===")
                        print(json.dumps(batch_btns, ensure_ascii=False, indent=2))
                        break
                break
        browser.close()

asyncio.run(main())
