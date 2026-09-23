"""探查1688铺货日志表格结构和分页"""
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

        # 检查表格行结构
        rows = await frame.evaluate("""
            () => {
                const tbody = document.querySelector('.distribution-list-table .ant-table-tbody') ||
                              document.querySelector('.ant-pro-table .ant-table-tbody') ||
                              document.querySelector('.ant-table-tbody');
                if (!tbody) {
                    // 尝试找所有行
                    const allRows = document.querySelectorAll('[class*="distribution"] tr, .ant-table-row');
                    return {found: false, msg: 'tbody not found', alt_rows: allRows.length};
                }
                const trs = tbody.querySelectorAll('tr');
                const results = [];
                for (const row of trs) {
                    const cells = row.querySelectorAll('td');
                    const btns = row.querySelectorAll('button');
                    const btnTexts = Array.from(btns).map(b => b.textContent.trim());
                    results.push({
                        cells: cells.length,
                        text: row.textContent.trim().substring(0, 150),
                        buttons: btnTexts,
                        row_key: row.getAttribute('data-row-key') || ''
                    });
                }
                return {found: true, row_count: trs.length, rows: results.slice(0, 3)};
            }
        """)
        print("=== 表格行 ===")
        print(json.dumps(rows, ensure_ascii=False, indent=2))

        # 分页
        pagination = await frame.evaluate("""
            () => {
                const pager = document.querySelector('.ant-pagination');
                if (!pager) return {found: false};
                return {
                    found: true,
                    text: pager.textContent.trim().substring(0, 200),
                    html: pager.outerHTML.substring(0, 500)
                };
            }
        """)
        print("\n=== 分页 ===")
        print(json.dumps(pagination, ensure_ascii=False, indent=2))

        # 找所有"编辑店铺草稿"按钮的位置
        edit_btns = await frame.evaluate("""
            () => {
                const btns = document.querySelectorAll('button');
                const results = [];
                for (const b of btns) {
                    if (b.textContent.includes('编辑店铺草稿')) {
                        const row = b.closest('tr');
                        results.push({
                            text: b.textContent.trim(),
                            class: b.className.substring(0, 60),
                            row_text: row?.textContent?.trim()?.substring(0, 100) || '',
                            row_key: row?.getAttribute('data-row-key') || ''
                        });
                    }
                }
                return {count: results.length, buttons: results.slice(0, 5)};
            }
        """)
        print("\n=== 编辑店铺草稿按钮 ===")
        print(json.dumps(edit_btns, ensure_ascii=False, indent=2))

asyncio.run(main())
