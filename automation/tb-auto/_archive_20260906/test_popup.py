"""测试点击编辑店铺草稿，检查弹框结构"""
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

        # 记录当前tab数量
        pages_before = len(browser.contexts[0].pages)
        print(f"点击前tab数量: {pages_before}")

        # 点击第一个"编辑店铺草稿"按钮
        btn = frame.locator('button:has-text("编辑店铺草稿")').first
        await btn.click()
        print("已点击'编辑店铺草稿'")
        await asyncio.sleep(3)

        # 检查弹框
        popup = await frame.evaluate("""
            () => {
                const modal = document.querySelector('.ant-modal, .ant-modal-content, [class*="modal"], [class*="dialog"], [class*="popup"]');
                if (!modal) return {found: false};
                const btns = modal.querySelectorAll('button, [role="button"]');
                return {
                    found: true,
                    class: modal.className.substring(0, 80),
                    text: modal.textContent.trim().substring(0, 300),
                    buttons: Array.from(btns).map(b => b.textContent.trim().substring(0, 30))
                };
            }
        """)
        print("\n=== 弹框 ===")
        print(json.dumps(popup, ensure_ascii=False, indent=2))

        # 检查是否打开了新tab
        pages_after = len(browser.contexts[0].pages)
        print(f"\n点击后tab数量: {pages_after}")
        for i, pg in enumerate(browser.contexts[0].pages):
            print(f"  Tab {i}: {pg.url[:80]}")

asyncio.run(main())
