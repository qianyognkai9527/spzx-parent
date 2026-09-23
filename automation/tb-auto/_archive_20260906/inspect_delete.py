"""探查铺货日志页面，找到删除/取消商品的操作"""
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
                        # 验证是否在铺货日志页
                        text = await f.evaluate('document.body?.innerText?.substring(0, 400) || ""')
                        has_log = '铺货失败' in text or '编辑店铺草稿' in text
                        print(f"在铺货日志页: {has_log}")
                        if has_log:
                            print(f"内容: {text[:200]}")
                            
                            # 检查筛选状态
                            if '最近30天' in text:
                                print("已筛选最近30天")
                            
                            # 检查表格行和操作按钮
                            rows = await f.evaluate("""
                                () => {
                                    const tbody = document.querySelector('.ant-table-tbody');
                                    if (!tbody) return {found: false};
                                    const trs = tbody.querySelectorAll('tr.ant-table-row');
                                    const results = [];
                                    for (const tr of trs) {
                                        const title = tr.textContent.substring(0, 60);
                                        const buttons = Array.from(tr.querySelectorAll('button')).map(b => b.textContent.trim());
                                        results.push({
                                            title: title,
                                            buttons: buttons,
                                            row_key: tr.getAttribute('data-row-key')
                                        });
                                    }
                                    return {found: true, count: results.length, rows: results.slice(0, 5)};
                                }
                            """)
                            print("\n=== 表格行(前5) ===")
                            print(json.dumps(rows, ensure_ascii=False, indent=2))
                            
                            # 检查是否有多选/批量操作
                            batch_ops = await f.evaluate("""
                                () => {
                                    // 找批量操作按钮/复选框
                                    const checkboxes = document.querySelectorAll('.ant-table-thead input[type="checkbox"], [class*="selection"]');
                                    const buttons = Array.from(document.querySelectorAll('button')).filter(b => {
                                        const t = b.textContent.trim();
                                        return t.includes('删除') || t.includes('取消') || t.includes('批量');
                                    }).map(b => ({text: b.textContent.trim(), class: b.className.substring(0, 40)}));
                                    return {
                                        header_checkboxes: checkboxes.length,
                                        delete_cancel_buttons: buttons
                                    };
                                }
                            """)
                            print("\n=== 批量操作 ===")
                            print(json.dumps(batch_ops, ensure_ascii=False, indent=2))
                            
                            # 检查"更多"菜单或操作列下拉
                            more_ops = await f.evaluate("""
                                () => {
                                    const dropdowns = document.querySelectorAll('[class*="dropdown"], [class*="more"], [class*="ellipsis"]');
                                    return Array.from(dropdowns).filter(d => d.offsetParent !== null).map(d => ({
                                        class: d.className.substring(0, 40),
                                        text: d.textContent.trim().substring(0, 30)
                                    })).slice(0, 10);
                                }
                            """)
                            print("\n=== 下拉/更多菜单 ===")
                            print(json.dumps(more_ops, ensure_ascii=False, indent=2))
                        break
                break
        browser.close()

asyncio.run(main())
